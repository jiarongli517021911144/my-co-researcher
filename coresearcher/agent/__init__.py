__all__ = ["AgentLoop"]


def __getattr__(name: str):
    if name == "AgentLoop":
        from coresearcher.agent.loop import AgentLoop

        return AgentLoop
    raise AttributeError(name)
