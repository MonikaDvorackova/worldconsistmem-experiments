"""Observation stream generation (structured gold + NL renderings)."""

from __future__ import annotations

from .generate import GeneratedWorld
from .models import Event, Observation


def _canonical_text(event: Event) -> str:
    p = event.payload
    et = event.event_type.value
    return f"[t={event.t}] {et}: {p} (prov={event.provenance_id})"


def _paraphrase_text(event: Event) -> str:
    p = event.payload
    et = event.event_type.value.replace("_", " ")
    bits = ", ".join(f"{k}={v}" for k, v in sorted(p.items()))
    return f"At revision {event.t}, the world recorded a {et} involving {bits}."


def render_observation(event: Event, world_id: str, distractor: bool = False) -> Observation:
    structured = {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "t": event.t,
        "actor_id": event.actor_id,
        "affected_ids": list(event.affected_ids),
        "payload": dict(event.payload),
        "provenance_id": event.provenance_id,
        "preconditions": list(event.preconditions),
    }
    return Observation(
        observation_id=f"{world_id}:obs:{event.t}" + (":d" if distractor else ""),
        event_id=event.event_id,
        t=event.t,
        provenance_id=event.provenance_id,
        structured=structured,
        text_canonical=_canonical_text(event),
        text_paraphrase=_paraphrase_text(event),
        is_distractor=distractor,
    )


def generate_observations(
    world: GeneratedWorld, include_distractors: bool = True
) -> list[Observation]:
    obs = [render_observation(e, world.world_id) for e in world.events]
    if include_distractors and world.events:
        # One distractor: paraphrase of an early event attached with distractor flag
        # (does not alter gold structured authority; marked is_distractor=True)
        e0 = world.events[0]
        d = render_observation(e0, world.world_id, distractor=True)
        d.observation_id = f"{world.world_id}:obs:distractor"
        d.text_canonical = f"DISTRACTOR rumor: {d.text_canonical}"
        d.text_paraphrase = f"Unverified rumor (ignore for gold): {d.text_paraphrase}"
        obs.append(d)
    return obs
