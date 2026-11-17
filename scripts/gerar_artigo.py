"""Monta o artigo em PDF: o texto vem de artigo/texto.md e os números, dos resultados salvos.

A equipe escreve o texto em artigo/texto.md. Este script só faz a montagem:
primeira página, seções, figuras e tabelas com legenda e fonte no padrão ABNT,
e as referências. Tabelas e figuras saem direto de artifacts/, então os números
delas sempre batem com os modelos.

Uso: python scripts/gerar_artigo.py
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fpdf import FPDF
from fpdf.enums import MethodReturnValue
from PIL import Image

# A Times New Roman Bold do macOS não tem o glifo ".notdef"; o fpdf2 avisa no log e usa um substituto.
# O aviso não muda nada no PDF, então só ele é escondido.
logging.getLogger("fpdf.fonts").addFilter(lambda registro: ".notdef" not in registro.getMessage())

from src.config import ARTIFACTS, CLASSES, FIGURAS, METRICAS, ROOT, nome_exibicao
from src.figuras import imagem_das_resolucoes

TEXTO = ROOT / "artigo" / "texto.md"
SAIDA = ROOT / "artigo" / "artigo.pdf"
LIMITE_PAGINAS = 10
ALTURA_LINHA = 5.6  # entrelinha do texto em 12 pt
FONTE_AUTORES = "Fonte: Elaborado pelos autores (2026)."
FONTE_IMAGENS = "Fonte: Elaborado pelos autores, com imagens do TrashNet (THUNG; YANG, 2016)."
ESPECIAIS = {"título", "autores", "repositório", "resumo", "palavras-chave", "referências"}
MARCAS_PENDENTES = ("[A EQUIPE ESCREVE", "[a preencher]", "[A PREENCHER")

# Margens ABNT: 3 cm à esquerda e em cima, 2 cm à direita e embaixo.
MARGEM_ESQ, MARGEM_DIR, MARGEM_SUP, MARGEM_INF = 30, 20, 30, 20
LARGURA_UTIL = 210 - MARGEM_ESQ - MARGEM_DIR
LIMITE_Y = 297 - MARGEM_INF

FONTES_TTF = [
    # Windows
    {"": r"C:\Windows\Fonts\times.ttf", "B": r"C:\Windows\Fonts\timesbd.ttf",
     "I": r"C:\Windows\Fonts\timesi.ttf", "BI": r"C:\Windows\Fonts\timesbi.ttf"},
    # macOS
    {"": "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
     "B": "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
     "I": "/System/Library/Fonts/Supplemental/Times New Roman Italic.ttf",
     "BI": "/System/Library/Fonts/Supplemental/Times New Roman Bold Italic.ttf"},
    # Linux com as fontes da Microsoft ou com a Liberation Serif (mesmas medidas da Times New Roman)
    {"": "/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman.ttf",
     "B": "/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman_Bold.ttf",
     "I": "/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman_Italic.ttf",
     "BI": "/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman_Bold_Italic.ttf"},
    {"": "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
     "B": "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
     "I": "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
     "BI": "/usr/share/fonts/truetype/liberation/LiberationSerif-BoldItalic.ttf"},
]


def num(valor: float, casas: int = 3) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def inteiro(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


def carregar(caminho: Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- leitura do texto


def ler_texto(caminho: Path) -> list[dict]:
    """Seções do texto.md. Cada seção tem título e blocos: parágrafo, subtítulo, figura ou tabela."""
    bruto = re.sub(r"<!--.*?-->", "", caminho.read_text(encoding="utf-8"), flags=re.S)
    secoes: list[dict] = []
    paragrafo: list[str] = []

    def fechar_paragrafo():
        if paragrafo and secoes:
            secoes[-1]["blocos"].append(("par", " ".join(paragrafo)))
        paragrafo.clear()

    for linha in bruto.splitlines():
        texto = linha.strip()
        if texto.startswith("# "):
            fechar_paragrafo()
            secoes.append({"titulo": texto[2:].strip(), "blocos": []})
        elif texto.startswith("## "):
            fechar_paragrafo()
            secoes[-1]["blocos"].append(("sub", texto[3:].strip()))
        elif re.fullmatch(r"\[\[(FIGURA|TABELA):([\w-]+)\]\]", texto):
            fechar_paragrafo()
            tipo, nome = re.fullmatch(r"\[\[(FIGURA|TABELA):([\w-]+)\]\]", texto).groups()
            secoes[-1]["blocos"].append(("fig" if tipo == "FIGURA" else "tab", nome))
        elif not texto:
            fechar_paragrafo()
        else:
            paragrafo.append(texto)
    fechar_paragrafo()
    return secoes


def secao(secoes: list[dict], titulo: str) -> list:
    for item in secoes:
        if item["titulo"].lower() == titulo:
            return item["blocos"]
    return []


def paragrafos(blocos: list) -> list[str]:
    return [conteudo for tipo, conteudo in blocos if tipo == "par"]


# ---------------------------------------------------------------- PDF


class Artigo(FPDF):
    def __init__(self):
        super().__init__(format="A4", unit="mm")
        self.familia = self._registrar_fontes()
        self.set_auto_page_break(auto=True, margin=MARGEM_INF)
        self.set_margins(left=MARGEM_ESQ, top=MARGEM_SUP, right=MARGEM_DIR)
        self.n_figura = 0
        self.n_tabela = 0
        self.pendencias: list[str] = []
        self.add_page()

    def _registrar_fontes(self) -> str:
        for conjunto in FONTES_TTF:
            if all(Path(caminho).is_file() for caminho in conjunto.values()):
                for estilo, caminho in conjunto.items():
                    self.add_font("Serif", estilo, caminho)
                return "Serif"
        # Sem Times New Roman nem Liberation Serif: fonte Times embutida no leitor de PDF.
        self.core_fonts_encoding = "windows-1252"
        return "Times"

    def header(self):
        # ABNT NBR 14724: número no canto superior direito, a 2 cm da borda de cima.
        self.set_xy(MARGEM_ESQ, 17)
        self.set_font(self.familia, "", 10)
        self.set_text_color(0, 0, 0)
        self.cell(LARGURA_UTIL, 5, str(self.page_no()), align="R")
        self.set_xy(MARGEM_ESQ, MARGEM_SUP)

    def escrever(self, conteudo: str, tamanho: float = 12, estilo: str = "", alinhamento: str = "J",
                 altura: float = ALTURA_LINHA):
        pendente = any(marca.lower() in conteudo.lower() for marca in MARCAS_PENDENTES)
        if pendente:
            self.pendencias.append(conteudo[:90])
            self.set_text_color(190, 0, 0)
        self.set_font(self.familia, estilo, tamanho)
        self.multi_cell(0, altura, conteudo, align=alinhamento, markdown=True,
                        new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)

    def paragrafo(self, conteudo: str):
        self.escrever(conteudo)
        self.ln(1.6)

    def titulo_secao(self, titulo: str, nivel: int = 1, centralizado: bool = False):
        if self.get_y() > LIMITE_Y - 25:
            self.add_page()
        self.ln(2.5 if nivel == 1 else 1.5)
        self.escrever(titulo, estilo="B" if nivel == 1 else "BI", alinhamento="C" if centralizado else "L")
        self.ln(1)

    def _altura_texto(self, texto: str, tamanho: float, largura: float, altura: float) -> float:
        self.set_font(self.familia, "", tamanho)
        return self.multi_cell(largura, altura, texto, dry_run=True, output=MethodReturnValue.HEIGHT)

    def altura_figura(self, caminho: Path, titulo: str, largura: float) -> float:
        with Image.open(caminho) as imagem:
            altura = largura * imagem.size[1] / imagem.size[0]
        legenda = self._altura_texto(f"Figura 00 - {titulo}", 10, LARGURA_UTIL, 4.8)
        return legenda + 0.8 + altura + 1 + 4.6 + 3

    def altura_tabela(self, titulo: str, cabecalho: list, linhas: list, nota: str | None = None,
                      altura: float = 4.6, **_) -> float:
        legenda = self._altura_texto(f"Tabela 00 - {titulo}", 10, LARGURA_UTIL, 4.8)
        rodape = 4.6 + (self._altura_texto(f"Nota: {nota}", 10, LARGURA_UTIL, 4.6) if nota else 0)
        return legenda + 0.8 + altura * (len(cabecalho) + len(linhas)) + 1 + rodape + 3

    def cabe(self, altura: float) -> bool:
        return self.get_y() + altura <= LIMITE_Y

    def _identificacao(self, tipo: str, titulo: str) -> None:
        self.set_font(self.familia, "", 10)
        self.multi_cell(0, 4.8, f"{tipo} {self.n_figura if tipo == 'Figura' else self.n_tabela} - {titulo}",
                        align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(0.8)

    def _rodape_ilustracao(self, fonte: str, nota: str | None = None, x: float | None = None) -> None:
        self.set_font(self.familia, "", 10)
        largura = LARGURA_UTIL - ((x or MARGEM_ESQ) - MARGEM_ESQ)
        if nota:
            self.set_x(x or MARGEM_ESQ)
            self.multi_cell(largura, 4.6, f"Nota: {nota}", align="L", new_x="LMARGIN", new_y="NEXT")
        self.set_x(x or MARGEM_ESQ)
        self.multi_cell(largura, 4.6, fonte, align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def figura(self, caminho: Path, titulo: str, fonte: str, largura: float = LARGURA_UTIL):
        if not self.cabe(self.altura_figura(caminho, titulo, largura)):
            self.add_page()
        self.n_figura += 1
        self._identificacao("Figura", titulo)
        x = MARGEM_ESQ + (LARGURA_UTIL - largura) / 2
        self.image(str(caminho), x=x, w=largura)
        self.ln(1)
        self._rodape_ilustracao(fonte, x=x)

    def tabela(self, titulo: str, cabecalho: list[list[tuple[str, int]]], linhas: list[list[str]],
               larguras: list[float], fonte: str = FONTE_AUTORES, nota: str | None = None,
               tamanho: float = 8.5, altura: float = 4.6, separar_a_cada: int | None = None):
        """Tabela no estilo IBGE: sem bordas laterais, com traços no topo, abaixo do cabeçalho e no fim."""
        assert abs(sum(larguras) - LARGURA_UTIL) < 0.5, sum(larguras)
        if not self.cabe(self.altura_tabela(titulo, cabecalho, linhas, nota, altura)):
            self.add_page()
        self.n_tabela += 1
        self._identificacao("Tabela", titulo)
        self.set_draw_color(0, 0, 0)
        self.set_line_width(0.3)
        self.line(MARGEM_ESQ, self.get_y(), MARGEM_ESQ + LARGURA_UTIL, self.get_y())
        self.set_font(self.familia, "B", tamanho)
        for linha in cabecalho:
            coluna = 0
            for texto, span in linha:
                self.cell(sum(larguras[coluna:coluna + span]), altura, texto, align="C")
                coluna += span
            self.ln()
        self.line(MARGEM_ESQ, self.get_y(), MARGEM_ESQ + LARGURA_UTIL, self.get_y())
        self.set_font(self.familia, "", tamanho)
        self.set_line_width(0.1)
        for indice, linha in enumerate(linhas):
            if separar_a_cada and indice and indice % separar_a_cada == 0:
                self.line(MARGEM_ESQ, self.get_y(), MARGEM_ESQ + LARGURA_UTIL, self.get_y())
            for coluna, (largura, valor) in enumerate(zip(larguras, linha)):
                self.cell(largura, altura, valor, align="L" if coluna == 0 else "C")
            self.ln()
        self.set_line_width(0.3)
        self.line(MARGEM_ESQ, self.get_y(), MARGEM_ESQ + LARGURA_UTIL, self.get_y())
        self.set_line_width(0.2)
        self.ln(1)
        self._rodape_ilustracao(fonte, nota)


# ---------------------------------------------------------------- figuras e tabelas


def montar_ilustracoes(resumo: dict, eda: dict, divisao: dict) -> tuple[dict, dict]:
    por_id = {item["id"]: item for item in resumo["experimentos"]}
    ordem = [item["id"] for item in resumo["experimentos"]]
    partes = divisao["partes"]
    registros = sorted(partes["treino"] + partes["validacao"] + partes["teste"],
                       key=lambda item: (item["rotulo"], item["caminho"]))
    imagem_res = imagem_das_resolucoes(registros)["caminho"]
    erros = resumo["erros"]

    figuras = {
        "distribuicao_classes": ("Quantidade de imagens por classe nos conjuntos de treino, validação e teste",
                                 FONTE_AUTORES),
        "exemplos_classes": ("Dois exemplos de cada classe, na ordem usada nas matrizes de confusão", FONTE_IMAGENS,
                             150),
        "exemplo_resolucoes": (f"A imagem {imagem_res} nas três resoluções de entrada da CNN", FONTE_IMAGENS, 130),
        "curvas_aprendizagem": (
            "Perda e acurácia de treino e validação por época nos seis experimentos. A linha tracejada marca "
            "a época do modelo salvo. A acurácia de treino é a média da época, com o dropout ativo",
            FONTE_AUTORES,
        ),
        "matrizes_confusao": (
            "Matrizes de confusão no conjunto de teste, com contagem e porcentagem da linha em cada célula. "
            "Linhas: classe real; colunas: classe prevista",
            FONTE_AUTORES,
        ),
        "efeito_resolucao": (
            "CNN sem pesos de classe nas três resoluções: (a) acurácia e F1 macro no teste; (b) pico de memória "
            "do processo de treino; (c) tempo médio por época; (d) tempo total de treinamento",
            FONTE_AUTORES,
        ),
        "erros_teste": (
            f"Erros de teste do modelo {nome_exibicao(erros['experimento'])}, o de maior F1 macro na validação: "
            f"{len(erros['amostras'])} dos {erros['total_erros_teste']} erros em {erros['total_teste']} imagens, "
            "ordenados pela probabilidade atribuída à classe prevista (p)",
            FONTE_IMAGENS,
        ),
    }

    desempenho = [
        [nome_exibicao(i), num(por_id[i]["acuracia_treino"]), num(por_id[i]["validacao"]["acuracia"]),
         num(por_id[i]["validacao"]["f1_macro"]), num(por_id[i]["teste"]["acuracia"]),
         num(por_id[i]["teste"]["f1_macro"])]
        for i in ordem
    ]
    custo = [
        [nome_exibicao(i), inteiro(por_id[i]["parametros"]), num(por_id[i]["tamanho_modelo_bytes"] / 1024**2, 1),
         str(por_id[i]["epocas_executadas"]), str(por_id[i]["epoca_modelo_salvo"]),
         num(por_id[i]["tempo_medio_epoca_s"], 1), num(por_id[i]["tempo_total_s"] / 60, 1),
         inteiro(por_id[i]["pico_memoria_bytes"] / 1024**2) if por_id[i]["pico_memoria_bytes"] else "-"]
        for i in ordem
    ]
    curtos = {"mlp_128x96": "MLP", "mlp_128x96_pesos": "MLP + p.", "cnn_128x96": "CNN 128",
              "cnn_128x96_pesos": "CNN 128 + p.", "cnn_256x192": "CNN 256", "cnn_512x384": "CNN 512"}
    por_classe = []
    for classe in CLASSES:
        suporte = next(c["suporte"] for c in por_id[ordem[0]]["teste"]["por_classe"] if c["classe"] == classe)
        linha = [classe, str(suporte)]
        for i in ordem:
            dados = next(c for c in por_id[i]["teste"]["por_classe"] if c["classe"] == classe)
            linha += [num(dados["precisao"], 2), num(dados["recall"], 2), num(dados["f1"], 2)]
        por_classe.append(linha)

    hardware = por_id[ordem[0]]["hardware"]
    tabelas = {
        "desempenho": dict(
            titulo="Desempenho dos seis experimentos nos conjuntos de treino, validação e teste",
            cabecalho=[[("", 1), ("Treino", 1), ("Validação", 2), ("Teste", 2)],
                       [("Experimento", 1), ("Acurácia", 1), ("Acurácia", 1), ("F1 macro", 1),
                        ("Acurácia", 1), ("F1 macro", 1)]],
            linhas=desempenho, larguras=[40, 24, 24, 24, 24, 24],
            nota=("a acurácia de treino foi calculada com o modelo salvo e o dropout desligado. "
                  "O modelo escolhido é o de maior F1 macro na validação."),
        ),
        "custo": dict(
            titulo=(f"Custo de treinamento dos seis experimentos ({hardware['processador']}, "
                    f"{inteiro(hardware['ram_total_gb'])} GB de RAM, só CPU, lote {por_id[ordem[0]]['lote']})"),
            cabecalho=[[("", 1), ("", 1), ("Modelo", 1), ("Épocas", 1), ("Época", 1), ("Tempo por", 1),
                        ("Tempo", 1), ("Pico de", 1)],
                       [("Experimento", 1), ("Parâmetros", 1), ("(MB)", 1), ("rodadas", 1), ("salva", 1),
                        ("época (s)", 1), ("total (min)", 1), ("memória (MB)", 1)]],
            linhas=custo, larguras=[36, 21, 15, 15, 14, 19, 19, 21],
            nota=("tempo de época do início ao fim da época, com a validação, sem download nem carga das imagens; "
                  "pico de memória informado pelo sistema para o processo do treino."),
        ),
        "por_classe": dict(
            titulo="Precisão (P), recall (R) e F1 por classe no conjunto de teste",
            cabecalho=[[("", 1), ("", 1)] + [(curtos[i], 3) for i in ordem],
                       [("Classe", 1), ("Suporte", 1)] + [("P", 1), ("R", 1), ("F1", 1)] * len(ordem)],
            linhas=por_classe, larguras=[19, 15] + [7] * 18,
            nota=("+ p. = com pesos de classe. Suporte é o número de imagens de cada classe no teste, igual em "
                  "todos os experimentos. Com zero_division=0, a precisão e o F1 de uma classe que não recebeu "
                  "nenhuma previsão valem 0."),
            tamanho=7.5,
        ),
    }
    return figuras, tabelas


# ---------------------------------------------------------------- montagem


def gerar(texto: Path = TEXTO, saida: Path = SAIDA) -> Path:
    if not texto.is_file():
        raise SystemExit(f"Não encontrei {texto}. É nele que a equipe escreve o texto.")
    secoes = ler_texto(texto)
    resumo = carregar(METRICAS / "resumo.json")
    figuras, tabelas = montar_ilustracoes(resumo, carregar(ARTIFACTS / "eda.json"), carregar(ARTIFACTS / "divisao.json"))

    pdf = Artigo()
    titulo = " ".join(paragrafos(secao(secoes, "título"))) or "[A EQUIPE ESCREVE O TÍTULO]"
    pdf.escrever(titulo, tamanho=14, estilo="B", alinhamento="C", altura=7)
    pdf.ln(3)
    for bloco in paragrafos(secao(secoes, "autores")):
        pdf.escrever(bloco, alinhamento="C", altura=5.6)
    pdf.ln(1)
    repositorio = " ".join(paragrafos(secao(secoes, "repositório")))
    pdf.escrever(f"Repositório: {repositorio}", tamanho=11, alinhamento="C", altura=5.4)
    pdf.ln(4)

    pdf.escrever("Resumo", estilo="B", alinhamento="C")
    pdf.ln(1)
    for bloco in paragrafos(secao(secoes, "resumo")):
        pdf.escrever(bloco, altura=5.4)
    pdf.ln(1.5)
    palavras = " ".join(paragrafos(secao(secoes, "palavras-chave")))
    pdf.escrever(f"**Palavras-chave:** {palavras}", altura=5.4, alinhamento="L")

    usadas: set[str] = set()
    # Figuras e tabelas que não cabem no resto da página esperam numa fila, na ordem, e o texto
    # seguinte preenche a página. Elas entram assim que houver espaço, como num editor de texto.
    fila: list[tuple[str, str]] = []

    def dados(tipo: str, nome: str):
        if tipo == "fig":
            titulo_fig, fonte, *largura = figuras[nome]
            return FIGURAS / f"{nome}.png", titulo_fig, fonte, (largura[0] if largura else LARGURA_UTIL)
        return tabelas[nome]

    def altura_de(tipo: str, nome: str) -> float:
        if tipo == "fig":
            caminho, titulo_fig, _, largura = dados(tipo, nome)
            return pdf.altura_figura(caminho, titulo_fig, largura)
        return pdf.altura_tabela(**dados(tipo, nome))

    def colocar(tipo: str, nome: str) -> None:
        if tipo == "fig":
            pdf.figura(*dados(tipo, nome))
            usadas.add(f"FIGURA:{nome}")
        else:
            pdf.tabela(**dados(tipo, nome))
            usadas.add(f"TABELA:{nome}")

    def esvaziar_fila(forcar: bool = False) -> None:
        while fila and (forcar or pdf.cabe(altura_de(*fila[0]))):
            colocar(*fila.pop(0))

    def pedir(tipo: str, nome: str) -> None:
        opcoes = figuras if tipo == "fig" else tabelas
        if nome not in opcoes:
            rotulo = "Figura" if tipo == "fig" else "Tabela"
            raise SystemExit(f"{rotulo} desconhecida em texto.md: {nome}. Opções: {', '.join(opcoes)}")
        if fila or not pdf.cabe(altura_de(tipo, nome)):
            fila.append((tipo, nome))
        else:
            colocar(tipo, nome)

    for item in secoes:
        nome = item["titulo"].lower()
        if nome in ESPECIAIS and nome != "referências":
            continue
        referencias = nome == "referências"
        esvaziar_fila(forcar=referencias)
        pdf.titulo_secao(item["titulo"], centralizado=referencias)
        for tipo, conteudo in item["blocos"]:
            if tipo == "sub":
                pdf.titulo_secao(conteudo, nivel=2)
            elif tipo == "par" and referencias:
                pdf.escrever(conteudo, tamanho=11, alinhamento="L", altura=5.0)
                pdf.ln(3.5)
            elif tipo == "par":
                pdf.paragrafo(conteudo)
                esvaziar_fila()
            elif tipo == "fig":
                if conteudo not in figuras:
                    raise SystemExit(f"Figura desconhecida em texto.md: {conteudo}. Opções: {', '.join(figuras)}")
                pedir("fig", conteudo)
            elif tipo == "tab":
                if conteudo not in tabelas:
                    raise SystemExit(f"Tabela desconhecida em texto.md: {conteudo}. Opções: {', '.join(tabelas)}")
                pedir("tab", conteudo)

    esvaziar_fila(forcar=True)
    saida.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(saida))

    faltando = [f"FIGURA:{n}" for n in figuras if f"FIGURA:{n}" not in usadas]
    faltando += [f"TABELA:{n}" for n in tabelas if f"TABELA:{n}" not in usadas]
    print(f"Artigo gravado em {saida}: {pdf.page} páginas (limite {LIMITE_PAGINAS}).")
    print(f"Fonte usada: {'Times New Roman ou equivalente embutida' if pdf.familia == 'Serif' else 'Times padrão do PDF'}.")
    if pdf.page > LIMITE_PAGINAS:
        print(f"ATENÇÃO: passou de {LIMITE_PAGINAS} páginas. Encurte o texto.")
    if faltando:
        print("ATENÇÃO: elementos exigidos que não aparecem no texto.md: " + ", ".join(faltando))
    if pdf.pendencias:
        print(f"PENDENTE: {len(pdf.pendencias)} trecho(s) marcados para a equipe escrever ou preencher:")
        for trecho in pdf.pendencias:
            print("  - " + trecho)
    return saida


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monta o artigo em PDF a partir de artigo/texto.md.")
    parser.add_argument("--texto", type=Path, default=TEXTO, help="Arquivo de texto (padrão: artigo/texto.md).")
    parser.add_argument("--saida", type=Path, default=SAIDA, help="PDF de saída (padrão: artigo/artigo.pdf).")
    argumentos = parser.parse_args()
    gerar(argumentos.texto, argumentos.saida)
