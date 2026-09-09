# Nexus

Nexus is a local-first autonomous multi-agent runtime.

It provides persistent agent sessions, durable working state,
resumable execution, local model integration, tool execution,
project workflows, runtime readiness checks, and autonomous
multi-agent orchestration.

## Requirements

- Python 3.11 or newer
- Ollama for the default local model provider
- A configured Nexus-compatible local model

## Install

With pip:

    pip install nexus

With the Nexus Homebrew tap:

    brew install origit892-stack/nexus/nexus-agent

## Verify

    nexus --version
    nexus doctor
    nexus --help

## Core commands

    nexus init
    nexus chat
    nexus run
    nexus auto
    nexus status
    nexus ready
    nexus doctor
    nexus project
    nexus session
    nexus models
    nexus providers
    nexus tools
    nexus mcp
    nexus memory
    nexus plugins
    nexus jobs

## Sessions

Nexus sessions preserve durable execution context across turns
and process restarts.

The Agent Shell supports durable working state, checkpoints,
pending and completed work, blockers, automatic checkpoints,
and session resumption.

## Local-first

Nexus is designed around local execution and local model
providers while retaining explicit tool, evidence, readiness,
and runtime contracts.
