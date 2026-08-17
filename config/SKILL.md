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
- **claude-sonnet-5**
- **grok-4.5**

## Device Configuration

- **Mac-Studio**:
  - Default Backend: MLX
  - Notes: Primary Mac device with best local performance.

- **Win-RTX3080**:
  - Default Backend: LM Studio
  - Notes: Primary Windows device with high-performance LM Studio model.

- **Shared Ollama Host**:
  - Notes: Optional dedicated Ollama server for shared access across devices.
