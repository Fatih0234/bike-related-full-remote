"""Phase 2 runner (bike issue categorization)."""

from __future__ import annotations

import hashlib
from typing import Optional

from erp.config import Settings
from erp.db.client import db_cursor
from erp.labeling.common.prompt_loader import load_prompt
from erp.labeling.common.schemas import Phase2Output, truncate_evidence, truncate_reasoning
from erp.labeling.llm.gemini import GeminiClient
from erp.utils.logging import get_logger


logger = get_logger(__name__)


def _llm_input(title: Optional[str], description_redacted: Optional[str]) -> str:
    title_text = (title or "").strip()
    desc_text = (description_redacted or "").strip()
    return f"{title_text}\n\n{desc_text}"


def _input_hash(llm_input: str) -> str:
    return hashlib.md5(llm_input.encode("utf-8")).hexdigest()


def run(
    limit: Optional[int] = None,
    dry_run: bool = False,
    prompt_version: Optional[str] = None,
    model_id: Optional[str] = None,
) -> None:
    """Run Phase 2 labeling (issue categorization)."""
    settings = Settings()
    prompt_version = prompt_version or settings.phase2_prompt_version
    model_id = model_id or settings.gemini_model_id

    prompt = load_prompt(phase=2, prompt_version=prompt_version)
    client = GeminiClient(settings)

    logger.info(
        "phase2.run.start",
        extra={"limit": limit, "dry_run": dry_run, "prompt_version": prompt_version, "model": model_id},
    )

    rows: list[tuple[str, Optional[str], Optional[str]]] = []
    select_sql = """
        with latest_p1 as (
          select distinct on (service_request_id)
            service_request_id, bike_related
          from public.event_phase1_labels
          order by service_request_id, created_at desc
        )
        select e.service_request_id, e.title, e.description_redacted
        from public.events e
        join latest_p1 p1 on p1.service_request_id = e.service_request_id
        where p1.bike_related = true
          and e.skip_llm = false
          and e.has_description = true
          and not exists (
            select 1
            from public.event_phase2_labels l
            where l.service_request_id = e.service_request_id
              and l.prompt_version = %s
              and l.input_hash = md5(coalesce(btrim(e.title), '') || '\n\n' || coalesce(btrim(e.description_redacted), ''))
          )
        order by e.requested_at desc
    """
    if limit is not None:
        select_sql += " limit %s"

    with db_cursor(settings) as cursor:
        cursor.execute(select_sql, (prompt_version, limit) if limit is not None else (prompt_version,))
        rows = list(cursor.fetchall())

    if not rows:
        logger.info("phase2.run.no_candidates")
        logger.info("phase2.run.complete", extra={"labeled": 0, "dry_run": dry_run})
        return

    labeled = 0
    skipped = 0
    failures = 0

    for service_request_id, title, description_redacted in rows:
        llm_input = _llm_input(title=title, description_redacted=description_redacted)
        if not llm_input:
            skipped += 1
            continue

        full_prompt = f"{prompt}\n\nINPUT:\n{llm_input}\n"
        output, latency_ms, attempts, error = client.generate_structured(full_prompt, Phase2Output)

        if output is None:
            failures += 1
            logger.warning(
                "phase2.label.failed",
                extra={
                    "service_request_id": service_request_id,
                    "attempts": attempts,
                    "latency_ms": latency_ms,
                    "error": error,
                },
            )
            continue

        evidence = truncate_evidence(output.evidence)
        reasoning = truncate_reasoning(output.reasoning)
        confidence = float(output.confidence)
        input_hash = _input_hash(llm_input)

        logger.info(
            "phase2.label.ok",
            extra={
                "service_request_id": service_request_id,
                "category": output.category,
                "confidence": confidence,
                "attempts": attempts,
                "latency_ms": latency_ms,
                "dry_run": dry_run,
            },
        )

        if dry_run:
            labeled += 1
            continue

        insert_sql = """
            insert into public.event_phase2_labels (
                service_request_id,
                model,
                prompt_version,
                input_hash,
                bike_issue_category,
                confidence,
                evidence,
                reasoning
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (service_request_id, prompt_version, input_hash) do nothing
        """
        with db_cursor(settings) as cursor:
            cursor.execute(
                insert_sql,
                (
                    service_request_id,
                    model_id,
                    prompt_version,
                    input_hash,
                    output.category,
                    confidence,
                    evidence,
                    reasoning,
                ),
            )
            inserted = cursor.rowcount or 0

        if inserted:
            labeled += 1
        else:
            skipped += 1

    logger.info(
        "phase2.run.complete",
        extra={"labeled": labeled, "skipped": skipped, "failures": failures, "dry_run": dry_run},
    )
