# Agentic Supervisor

A **hierarchical multi-agent AI system** for safely routing, reasoning, and executing user requests across multiple domains such as **Calendar** and **Gmail**.

This project implements a **Supervisor-first architecture** with strict separation between planning, perception, and execution, inspired by real-world agentic AI systems rather than ad-hoc tool calling.

---

## 🧠 Why This Project?

Modern LLM-based systems often mix:
- reasoning
- tool execution
- memory
- side effects

This leads to:
- unsafe tool usage
- hard-to-debug behavior
- uncontrolled agent autonomy

**Agentic Supervisor** solves this by enforcing a clear hierarchy:

> **Supervisor decides → Agents reason → Tools execute**

---

## 🏗️ Architecture Overview

The system is organized into **four clear layers**:

### 1️⃣ Supervisor Layer
- Single entry point for all user requests
- Uses a Main Planner to decide the execution strategy
- Routes requests into one of three safe paths:
  - `respond_only` – pure LLM response
  - `perceive_only` – read-only context gathering
  - `perceive_then_act` – safe action execution

### 2️⃣ Reasoning Layer
- Performs perception and planning
- Extracts structured tasks from natural language
- Delegates work to specialist agents
- Never executes tools directly

### 3️⃣ Agent Layer
- Domain-specific intelligent agents (Calendar, Gmail)
- Convert high-level intent into concrete tool calls
- Stateless and deterministic

### 4️⃣ Tool Layer
- Low-level API and utility functions
- No reasoning, no memory, no autonomy
- Executes exactly what it is told

---

## 🔄 Execution Pipeline

For action-based requests, the system follows a **Perceive → Plan → Act** flow:

1. **Perceive**  
   Safely fetch minimal required context (calendar events, emails)

2. **Plan**  
   Convert intent + context into explicit executable steps

3. **Act**  
   Execute tools in parallel with nested execution support

This design prevents hallucinated actions and unsafe tool usage.

---

## 🧠 Memory Philosophy

The current implementation intentionally uses **only short-term execution memory**, keeping the system:

- deterministic
- debuggable
- safe

The architecture is designed to support future memory phases:

- **Phase 1:** ChatGPT-style semantic user memory  
- **Phase 2:** Episodic reflection and learning  
- **Phase 3:** Controlled self-improving behavior  

Memory will be introduced **only at the Supervisor level**, without modifying agents or tools.

---

## 📂 Project Structure

core/ # Message types and communication protocols
MainPlanner/ # High-level execution routing
planner/ # Task extraction and planning
supervisor/ # Orchestration and execution control
tools/
├── calendar/ # Calendar agent and functions
└── gmail/ # Gmail agent, query engine, and sender


---

## ✨ Key Design Principles

- **Strict hierarchy** – higher layers decide, lower layers execute
- **Stateless agents** – no hidden memory or side effects
- **Tool safety** – tools cannot reason or self-modify
- **Observability** – clear logs and execution traces
- **Extensibility** – easy to add new domains and agents

---

## 🎯 Use Cases

- Personal AI assistants (Calendar, Email, Tasks)
- Agentic AI research and experimentation
- Safe tool-calling frameworks
- Multi-agent orchestration systems
- Foundations for memory-aware AI assistants

---

## 🚀 Current Status

- ✅ Hierarchical execution pipeline implemented
- ✅ Multi-domain agent delegation (Calendar, Gmail)
- ✅ Parallel and nested tool execution
- 🟡 Semantic user memory (planned)
- 🔵 Self-improving behavior (future)

---

## ⚠️ Disclaimer

This project is an **experimental agentic architecture** intended for learning, research, and controlled applications.  
Use caution when connecting real-world tools or APIs.

---


