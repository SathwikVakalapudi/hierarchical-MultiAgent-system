# 🧠 Agentic Supervisor

A **hierarchical multi-agent AI system** for safely routing, reasoning, and executing user requests across domains like **Gmail** and **Google Calendar**.

> 🎥 Demo: https://youtu.be/b170aQGleoI

---

## 🚀 Overview

**Agentic Supervisor** implements a **Supervisor-first architecture** that enforces strict separation between:

- reasoning
- planning
- perception
- execution

Unlike typical LLM systems that mix everything together, this design ensures:

✅ safer tool usage  
✅ deterministic behavior  
✅ modular scalability  
✅ production-grade reliability  

---

## 🧠 Why This Project?

Most LLM-based agents today suffer from:

- ❌ hallucinated tool calls  
- ❌ unsafe execution  
- ❌ tightly coupled reasoning + acting  
- ❌ poor observability  

This project solves these issues with a **clear hierarchical control system**:

> **Supervisor decides → Agents reason → Tools execute**

---

## 🏗️ Architecture Overview

The system is organized into **four layers**:

### 1️⃣ Supervisor Layer
- Central control unit for all requests  
- Determines execution strategy  
- Routes requests into:
  - `respond_only`
  - `perceive_only`
  - `perceive_then_act`

---

### 2️⃣ Reasoning Layer
- Extracts structured tasks from natural language  
- Performs planning and decomposition  
- Delegates to domain-specific agents  
- ❗ Never executes tools  

---

### 3️⃣ Agent Layer
- Domain-specific agents (Gmail, Calendar)  
- Converts intent → executable actions  
- Stateless and deterministic  

---

### 4️⃣ Tool Layer
- Executes API calls and utilities  
- No reasoning, no autonomy  
- Fully controlled by higher layers  

---

## 🔄 Execution Pipeline

For action-based tasks, the system follows:

### **Perceive → Plan → Act**

1. **Perceive**
   - Fetch minimal required context (emails, events)

2. **Plan**
   - Convert intent into structured execution steps

3. **Act**
   - Execute tools safely (parallel + nested execution supported)

---

## 🧪 Example Flow

**Input:**
