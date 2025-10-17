# Start Here Notebooks

Introductory walkthroughs that build up the Agent Framework workflow basics step by step.

## step1_executors_and_edges.ipynb

**Summary:** Connect two workflow executors: one uppercases text, the other reverses it and yields the final output. Along the way you learn how handlers work and how `WorkflowBuilder` wires nodes together. Key ingredients: `Executor` subclasses expose async handlers decorated with `@handler`; `@executor` turns a standalone function into a node; `WorkflowBuilder` creates a graph and its `run()` call collects yielded outputs.

```mermaid
flowchart LR
    Start(["Input Text"]) --> Upper[[UpperCase Executor]]
    Upper --> Reverse[[reverse_text executor]]
    Reverse --> Output(["Workflow Output"])
```

## step2_agents_in_a_workflow.ipynb

**Summary:** A Writer agent drafts a slogan, then a Reviewer agent critiques it. The workflow simply connects the two and prints what each agent says along with the final output list. Key ingredients: Azure-hosted chat agents created via `AzureOpenAIChatClient`; `WorkflowBuilder` wiring without custom executors-agents themselves can act as nodes; Event iteration over `AgentRunEvent` objects to display intermediate agent messages.

```mermaid
flowchart LR
    Start(["User Prompt"]) --> Writer[[Writer Agent]]
    Writer --> Reviewer[[Reviewer Agent]]
    Reviewer --> Output(["Workflow Outputs"])
```

## step3_streaming.ipynb

**Summary:** A Writer agent generates content, a Reviewer agent finalizes it, and `run_stream()` lets you watch every workflow event as it happens. Key ingredients: Custom executor classes that wrap `ChatAgent` instances; Typed `WorkflowContext` usage for both sending messages and yielding outputs; Streaming event loop that prints status transitions, outputs, and failures.

```mermaid
graph TD
    A[User Input<br/>ChatMessage] --> B[Writer Executor<br/>Content Generation Agent]
    B --> C[Reviewer Executor<br/>Content Review Agent]
    C --> D[Final Output<br/>Reviewed Text]

    subgraph "Workflow Details"
        E[Writer receives ChatMessage<br/>Creates content<br/>Forwards conversation to Reviewer]
        F[Reviewer receives full conversation<br/>Reviews and refines content<br/>Yields final output]
    end

    B -.-> E
    C -.-> F

    style A fill:#e1f5fe
    style B fill:#f3e5f5
    style C fill:#e8f5e8
    style D fill:#fff3e0
```

This diagram shows the flow created by:
```python
workflow = WorkflowBuilder().set_start_executor(writer).add_edge(writer, reviewer).build()
```
