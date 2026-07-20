# posfiap_7iadt_techchallenge_fase5
Tech Challenge da Fase 5 (Hackaton): análise de arquitetura com IA e aplicando insights de segurança com modelo STRIDE

## Extração de diagrama (`POST /api/v1/extraction/diagram`)

A extração de um `ArchitectureDiagram` a partir de uma imagem é feita pelo
detector de visão computacional em [`models/vision-detector`](models/vision-detector/README.md)
(YOLOv8), orquestrado pelo contrato de dados em [`extraction/`](extraction/README.md).
Ver [`docs/development.md`](docs/development.md#extração-de-diagrama-vision-detector)
para como subir, configurar GPU ou importar o modelo direto sem Docker.
