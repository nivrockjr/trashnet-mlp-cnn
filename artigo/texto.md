<!--
TEXTO DO ARTIGO. A equipe edita este arquivo e depois roda:
    python scripts/gerar_artigo.py
O PDF sai em artigo/artigo.pdf.

Como escrever aqui:
- Cada linha que começa com "# " abre uma seção; "## " abre uma subseção.
  Não mude o nome das seções Título, Autores, Repositório, Resumo, Palavras-chave e Referências.
- Parágrafos são separados por uma linha em branco.
- **texto** sai em negrito e __texto__ (dois sublinhados de cada lado) sai em itálico.
- As linhas [[FIGURA:...]] e [[TABELA:...]] colocam as figuras e tabelas, com número, legenda e fonte.
  Elas são numeradas na ordem em que aparecem. Se mudar a ordem, confira os números citados no texto.
- Tudo o que começa com [A EQUIPE ESCREVE ou [A PREENCHER sai em vermelho no PDF,
  e o script avisa no fim. Antes de entregar, não pode sobrar nenhum.
- Limite do enunciado: 10 páginas, uma coluna, com figuras, tabelas e referências.
- Comentários como este não aparecem no PDF.
-->

# Título

Classificação de resíduos em imagens do TrashNet: MLP, CNN, pesos de classe e resolução

# Autores

[A PREENCHER: Nome completo do integrante 1, matrícula 0000000]

[A PREENCHER: Nome completo do integrante 2, matrícula 0000000]

[A PREENCHER: Nome completo do integrante 3, matrícula 0000000]

[A PREENCHER: Nome completo do integrante 4, matrícula 0000000]

Universidade de Fortaleza (UNIFOR), Redes Neurais Artificiais, novembro de 2026

# Repositório

https://github.com/nivrockjr/trashnet-mlp-cnn

# Resumo

[A EQUIPE ESCREVE O RESUMO: um parágrafo de 100 a 250 palavras com o objetivo, o que foi feito (dados, modelos e experimentos), os principais números (modelo escolhido e seu F1 macro no teste) e a principal conclusão.]

# Palavras-chave

redes neurais; classificação de imagens; TrashNet; desequilíbrio de classes; custo computacional.

# 1 Introdução

[A EQUIPE ESCREVE A INTRODUÇÃO: dois ou três parágrafos com o contexto (separar resíduos para reciclagem), a motivação e o objetivo do estudo: comparar MLP e CNN em condições iguais, medir o efeito dos pesos de classe na classe trash e verificar se resoluções maiores compensam o custo. Citem o dataset (THUNG; YANG, 2016) e o artigo de referência (YANG; THUNG, 2016).]

# 2 Materiais e métodos

## 2.1 Dados

Foi usado apenas o arquivo dataset-resized.zip do repositório TrashNet (THUNG; YANG, 2016), com 2.527 imagens JPEG RGB de 512 × 384 pixels em seis classes: glass (501), paper (594), cardboard (403), plastic (482), metal (410) e trash (137). Segundo os autores do dataset, cada foto mostra um objeto sobre um cartaz branco, com luz do sol ou do ambiente. Na inspeção, todas as imagens foram abertas: nenhuma estava corrompida, e todas tinham o mesmo tamanho e o mesmo modo de cor.

A divisão foi estratificada por classe, com semente 42: 30% das imagens foram separadas do treino e depois divididas ao meio, também de forma estratificada, entre validação e teste. Ficaram 1.768 imagens de treino, 379 de validação e 380 de teste; a classe trash ficou com 96, 21 e 20. Cada arquivo está em um só conjunto, e a mesma divisão foi usada nos seis experimentos (Figura 1). A Figura 2 mostra dois exemplos de cada classe.

[[FIGURA:distribuicao_classes]]

[[FIGURA:exemplos_classes]]

## 2.2 Pré-processamento

As imagens foram convertidas para RGB e redimensionadas com interpolação bilinear para 128 × 96, 256 × 192 ou 512 × 384 pixels (Figura 3). A normalização é fixa, (pixel / 255) - 0,5, igual em treino, validação e teste, sem média ou desvio calculados nos dados. Essa escolha veio de um ensaio auxiliar feito só na validação: com os pixels apenas divididos por 255, a MLP 128 × 96 previu paper para todas as 379 imagens (acurácia 0,235 e F1 macro 0,063), enquanto a mesma rede com a normalização adotada teve acurácia 0,451 e F1 macro 0,374. A média dos pixels de treino, depois da divisão por 255, foi 0,639. Não houve aumento de dados.

[[FIGURA:exemplo_resolucoes]]

## 2.3 Arquiteturas

Na MLP, a imagem de 128 × 96 pixels vira um vetor de 36.864 valores (128 × 96 × 3). Há duas camadas ocultas, com 128 e 64 neurônios e ativação ReLU, inicialização de He (HE et al., 2015) e dropout de 0,3 (SRIVASTAVA et al., 2014) depois de cada uma, e uma saída softmax com seis neurônios. São 4.727.366 parâmetros, quase todos na primeira camada.

A CNN tem três blocos, cada um com uma convolução 3 × 3 (32, 64 e 128 filtros, ReLU) seguida de max pooling 2 × 2. Depois vêm um global average pooling, uma camada densa de 64 neurônios com ReLU, dropout de 0,3 e a mesma saída softmax. São 101.894 parâmetros nas três resoluções, porque o global average pooling entrega sempre um vetor de 128 valores à camada densa. No Keras, a entrada segue altura × largura × canais: 96 × 128 × 3, 192 × 256 × 3 e 384 × 512 × 3.

## 2.4 Treinamento e seleção

Os seis treinos usaram TensorFlow (ABADI et al., 2016) com Keras (CHOLLET et al., 2015), otimizador Adam (KINGMA; BA, 2015) com taxa de aprendizagem 0,001, entropia cruzada categórica esparsa, lote 16 e semente 42. O teto foi de 60 épocas, com parada antecipada pela perda de validação: paciência de 5 épocas e melhora mínima de 0,0001. O modelo salvo é o da época de menor perda de validação, como descrito no material da disciplina (BARBOSA, 2025).

Nos experimentos com pesos de classe, cada classe recebeu peso inversamente proporcional à sua frequência no treino, pela opção balanced do scikit-learn (PEDREGOSA et al., 2011): 3,07 para trash e 0,71 para paper, por exemplo. Validação e teste não entram nesse cálculo.

O modelo escolhido entre os seis é o de maior F1 macro na validação. O conjunto de teste só foi avaliado depois dessa escolha, uma única vez e sem novos ajustes. As métricas por classe usam zero_division=0: quando uma classe não recebe nenhuma previsão, a precisão e o F1 dela valem 0.

## 2.5 Ambiente e medição de custo

Os treinos rodaram num Mac com processador Apple M2 (8 núcleos) e 8 GB de RAM, com macOS 27.0 e Python 3.12.4, só na CPU, porque o TensorFlow não encontrou GPU. Cada experimento rodou sozinho, num processo próprio. O tempo de cada época vai do início ao fim da época, com a validação, e não inclui o download, a divisão nem a carga das imagens. O pico de memória é o maior valor informado pelo macOS para o processo do treino, incluindo o TensorFlow e as imagens carregadas. Não houve GPU, portanto não há memória de GPU a registrar. Na mesma máquina, os seis treinos repetidos geraram modelos idênticos. As métricas foram calculadas com scikit-learn; as tabelas e figuras, com NumPy (HARRIS et al., 2020), pandas (MCKINNEY, 2010) e Matplotlib (HUNTER, 2007); e as imagens foram lidas com Pillow (CLARK et al., 2015).

# 3 Resultados

A Tabela 1 mostra o desempenho dos seis experimentos e a Tabela 2, o custo de cada treino. Os seis pararam pela paciência, antes do teto de 60 épocas. O maior F1 macro de validação foi o da CNN 256 × 192 (0,732), que é o modelo escolhido; no teste, ele teve acurácia 0,755 e F1 macro 0,718.

[[TABELA:desempenho]]

[[TABELA:custo]]

A Tabela 3 detalha precisão, recall e F1 por classe no teste. A MLP 128 × 96 sem pesos não previu trash para nenhuma imagem de validação nem de teste; por isso, com zero_division=0, a precisão e o F1 de trash desse modelo valem 0.

[[TABELA:por_classe]]

A Figura 4 traz as curvas de aprendizagem, e a Figura 5, as matrizes de confusão no teste. A Figura 6 compara as três resoluções da CNN sem pesos. A Figura 7 mostra seis dos 93 erros do modelo escolhido nas 380 imagens de teste.

[[FIGURA:curvas_aprendizagem]]

[[FIGURA:matrizes_confusao]]

[[FIGURA:efeito_resolucao]]

[[FIGURA:erros_teste]]

# 4 Discussão

## 4.1 Arquiteturas

[A EQUIPE ESCREVE: como MLP e CNN se comportaram em 128 × 96 nas mesmas condições, com e sem pesos, e o que as curvas mostram sobre aprendizagem e sobreajuste.]

## 4.2 Desequilíbrio de classes

[A EQUIPE ESCREVE: como os pesos de classe mudaram trash e as outras classes em cada arquitetura, com ganhos e perdas.]

## 4.3 Resolução e custo

[A EQUIPE ESCREVE: se as resoluções maiores da CNN compensaram o aumento de tempo e de memória, comparando tempo médio por época e tempo total.]

## 4.4 Erros, aplicação e limitações

[A EQUIPE ESCREVE: quais classes foram confundidas, que características visuais podem explicar os erros e que limitações do dataset dificultam o uso em fotos de situações reais.]

## 4.5 Comparação com Yang e Thung (2016)

[A EQUIPE ESCREVE: os resultados do artigo de referência (63% com SVM em seis classes e 22% com CNN em cinco classes, sem trash) e as diferenças de classes, divisão, resolução e treinamento que impedem tratar os números como o mesmo experimento.]

# 5 Conclusão

[A EQUIPE ESCREVE A CONCLUSÃO: os principais achados e as melhorias que as evidências sugerem.]

# Referências

ABADI, Martín et al. **TensorFlow**: large-scale machine learning on heterogeneous distributed systems. [S. l.]: arXiv, 2016. Disponível em: https://arxiv.org/abs/1603.04467. Acesso em: 17 nov. 2026.

BARBOSA, Paulo Cirillo Souza. **Redes neurais multicamadas e algoritmos de treinamento**. Fortaleza: Universidade de Fortaleza, 2025. Material de leitura do percurso 2 da disciplina Redes Neurais Artificiais.

CHOLLET, François et al. **Keras**. [S. l.], 2015. Disponível em: https://keras.io. Acesso em: 17 nov. 2026.

CLARK, Alex et al. **Pillow (PIL Fork) documentation**. [S. l.], 2015. Disponível em: https://pillow.readthedocs.io. Acesso em: 17 nov. 2026.

HARRIS, Charles R. et al. Array programming with NumPy. **Nature**, London, v. 585, n. 7825, p. 357-362, 2020.

HE, Kaiming et al. Delving deep into rectifiers: surpassing human-level performance on ImageNet classification. In: IEEE INTERNATIONAL CONFERENCE ON COMPUTER VISION, 2015, Santiago. **Proceedings** [...]. Piscataway: IEEE, 2015. p. 1026-1034.

HUNTER, John D. Matplotlib: a 2D graphics environment. **Computing in Science & Engineering**, v. 9, n. 3, p. 90-95, 2007.

KINGMA, Diederik P.; BA, Jimmy. Adam: a method for stochastic optimization. In: INTERNATIONAL CONFERENCE ON LEARNING REPRESENTATIONS, 3., 2015, San Diego. **Proceedings** [...]. [S. l.: s. n.], 2015. Disponível em: https://arxiv.org/abs/1412.6980. Acesso em: 17 nov. 2026.

MCKINNEY, Wes. Data structures for statistical computing in Python. In: PYTHON IN SCIENCE CONFERENCE, 9., 2010, Austin. **Proceedings** [...]. Austin: SciPy, 2010. p. 56-61.

PEDREGOSA, Fabian et al. Scikit-learn: machine learning in Python. **Journal of Machine Learning Research**, v. 12, p. 2825-2830, 2011.

SRIVASTAVA, Nitish et al. Dropout: a simple way to prevent neural networks from overfitting. **Journal of Machine Learning Research**, v. 15, n. 56, p. 1929-1958, 2014.

THUNG, Gary; YANG, Mindy. **TrashNet**. [S. l.], 2016. Repositório de dados e código. Disponível em: https://github.com/garythung/trashnet. Acesso em: 17 nov. 2026.

YANG, Mindy; THUNG, Gary. **Classification of trash for recyclability status**. Stanford: Stanford University, 2016. Relatório de projeto da disciplina CS229. Disponível em: https://cs229.stanford.edu/proj2016/report/ThungYang-ClassificationOfTrashForRecyclabilityStatus-report.pdf. Acesso em: 17 nov. 2026.
