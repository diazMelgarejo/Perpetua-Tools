# SKILL.md - Model Registry and Device Configuration

## Overview

This document outlines the model registry and device configuration for the ECC-tools ecosystem. Each device (Mac, Windows, shared Ollama) can run multiple backends (`ollama`, `mlx`, `lm-studio`), and each model is prioritized based on performance and availability.

## Models

### Local Models

- **qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2** (Canonical Model for Windows):
  - Backend: LM Studio
  - Device: Win-RTX3080
  - Priority: 5
  - Roles: coder, coding, subagent, priority-subagent, checker, refiner, executor, verifier

- **qwen3.5:35b-a3b-q4_K_M** (Fallback Model):
  - Backend: Ollama
  - Device: Shared Ollama Host
  - Priority: 10
  - Notes: Known backup fallback model available.

### Online Models

- **sonar-reasoning-pro**
- **claude-sonnet-5-5** (Anthropic default, medium effort; `claude-sonnet-5` is a legacy pin)
- **grok-4.6** (direct-xAI last-resort; medium reasoning; `grok-4.5` is banned)

Harness defaults (Cursor vs Anthropic vs direct-xAI) live in
`config/model-governance.yml`. Cite Alexandria; do not copy the standard.

## Device Configuration

- **Mac-Studio**:
  - Default Backend: MLX
  - Notes: Primary Mac device with best local performance.

- **Win-RTX3080**:
  - Default Backend: LM Studio
  - Notes: Primary Windows device with high-performance LM Studio model.

- **Shared Ollama Host**:
  - Notes: Optional dedicated Ollama server for shared access across devices.
