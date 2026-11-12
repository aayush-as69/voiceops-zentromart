# VoiceOps Documentation

Technical documentation for the VoiceOps — ZentroMart AI Customer Support Assistant.

## Documentation map

| Document | Purpose |
|---|---|
| [Architecture](ARCHITECTURE.md) | End-to-end text and voice request flow |
| [Setup](SETUP.md) | Local installation, environment and dataset configuration |
| [RAG](RAG.md) | Retrieval pipeline, evidence handling and evaluation |
| [Voice pipeline](VOICE.md) | Gnani STT/TTS integration and audio workflow |
| [Evaluation](EVALUATION.md) | Practice-set metrics and how to reproduce them |
| [Testing](TESTING.md) | Automated test and validation commands |
| [Deployment](DEPLOYMENT.md) | Local and hosted deployment guidance |
| [Security & limitations](SECURITY.md) | Authentication boundary, secrets, data handling and known limitations |

## Architecture

```text
Browser / batch audio
        │
        ▼
    FastAPI app
        │
        ├── Text turn ───────────────┐
        │                            ▼
        └── Audio → Gnani STT → Support agent
                                     │
                         ┌───────────┼───────────┐
                         ▼           ▼           ▼
                      Retrieval    Policy      Tools
                         │           │           │
                         └───────────┼───────────┘
                                     ▼
                              LLM generation
                                     │
                         ┌───────────┴───────────┐
                         ▼                       ▼
                    Text reply              Gnani TTS
                                                 │
                                                 ▼
                                           Audio reply
```

The retrieval layer is currently lexical TF-IDF/cosine similarity. It is not a dense neural embedding/vector database implementation. Evaluation numbers must therefore be described as retrieval/evidence metrics for the configured corpus, not as proof of general-world factual accuracy.

## Source-of-truth rule

The repository code, tests and current dataset validator are authoritative. Evaluation figures in documentation must be regenerated after agent, retrieval, prompt, tool or dataset changes.

Credentials, the course dataset and private recordings must never be committed.