# Yasin Core Architecture


## Overview

Yasin Core is the central runtime layer of the Yasin AI Ecosystem.


## Main Components


### Runtime

Responsible for:

- Starting system
- Managing lifecycle
- Providing core services


### Event Bus

Provides internal communication between modules.


Example:

YasinRelay

emits:

NEW_CONTENT


YasinPress

receives event.


### Plugin System

Allows extending Yasin Core without changing the kernel.


### Provider Layer

Provides abstraction for AI models.


Future providers:

- OpenAI
- Ollama
- HuggingFace
- Local Models
