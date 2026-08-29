"""One run, end to end, with every stage behind a switch.

The switches are the point. Each one turns off a component that costs money and complexity, and the
evaluation runs the whole thing again with it off. A component that does not move the number does
not belong in the system, and the only way to know is to be able to remove it cleanly.

The order is fixed and it matters. Compilation produces criteria; terminology resolution attaches
codes to the concepts inside them, because nothing can match evidence without a code; the critic
reads the result back and downgrades anything that drifted. Only then is a patient touched, and by
then no model is involved at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from caliper.agents.base import AgentContext
from caliper.agents.compiler import CompileResult, compile_criteria
from caliper.agents.critic import CriticReport, apply_findings, review
from caliper.agents.resolver import resolve_concepts
from caliper.agents.writer import RationaleSet, deterministic_rationales, write_rationales
from caliper.evaluate import AbsencePolicy
from caliper.ir import Code, CriteriaSet, concepts_in, with_codes
from caliper.record import PatientIndex
from caliper.screen import ScreeningResult, screen
from caliper.wire import DEFAULT_DEPTH


@dataclass(frozen=True)
class PipelineConfig:
    """Which parts of the system are switched on for this run.

    The defaults are the shipping configuration. Every other combination exists so the evaluation
    can attribute the result to a component rather than to the system as a whole.
    """

    compile_depth: int = DEFAULT_DEPTH
    use_resolver: bool = True
    use_critic: bool = True
    write_rationales: bool = True
    absence_policy: AbsencePolicy = AbsencePolicy.COVERAGE_GATED

    @property
    def label(self) -> str:
        """A short name for this arm, for results tables and run directories."""
        if self.is_full:
            return "caliper"
        off = [
            name
            for name, on in (
                ("resolver", self.use_resolver),
                ("critic", self.use_critic),
                ("rationales", self.write_rationales),
            )
            if not on
        ]
        default_policy = self.absence_policy is AbsencePolicy.COVERAGE_GATED
        policy = [] if default_policy else [self.absence_policy.value]
        return "-".join(["caliper", *(f"no-{n}" for n in off), *policy]) or "caliper"

    @property
    def is_full(self) -> bool:
        return (
            self.use_resolver
            and self.use_critic
            and self.write_rationales
            and self.absence_policy is AbsencePolicy.COVERAGE_GATED
        )


DEFAULT_CONFIG = PipelineConfig()
"""The shipping configuration. Named so it can be a default argument without being rebuilt."""


@dataclass(frozen=True)
class CompiledTrial:
    """A protocol turned into criteria, with everything that happened on the way."""

    nct_id: str
    criteria_set: CriteriaSet
    compilation: CompileResult
    config: PipelineConfig
    resolved_codes: dict[str, tuple[Code, ...]] | None = None
    critic_report: CriticReport | None = None

    @property
    def unsupported_count(self) -> int:
        return self.criteria_set.unsupported_count


@dataclass(frozen=True)
class Screening:
    trial: CompiledTrial
    result: ScreeningResult
    rationales: RationaleSet | None = None


def compile_trial(
    nct_id: str,
    criteria_text: str,
    ctx: AgentContext,
    config: PipelineConfig = DEFAULT_CONFIG,
) -> CompiledTrial:
    """Compile one protocol, then resolve and check it according to `config`.

    Compilation happens once per trial and is reused across every patient screened against it,
    which is why the expensive parts of this system are cheap in aggregate.
    """
    compilation = compile_criteria(nct_id, criteria_text, ctx, depth=config.compile_depth)
    criteria_set = compilation.criteria_set

    resolved: dict[str, tuple[Code, ...]] | None = None
    if config.use_resolver and criteria_set.criteria:
        resolved = resolve_concepts(concepts_in(criteria_set), ctx, nct_id=nct_id)
        criteria_set = with_codes(criteria_set, resolved)

    report: CriticReport | None = None
    if config.use_critic and criteria_set.criteria:
        report = review(criteria_set, ctx)
        criteria_set = apply_findings(criteria_set, report)

    return CompiledTrial(
        nct_id=nct_id,
        criteria_set=criteria_set,
        compilation=compilation,
        config=config,
        resolved_codes=resolved,
        critic_report=report,
    )


def screen_patient(
    trial: CompiledTrial,
    patient: PatientIndex,
    as_of: date,
    ctx: AgentContext,
    config: PipelineConfig = DEFAULT_CONFIG,
) -> Screening:
    """Screen one patient against one compiled trial.

    The verdict is produced by `caliper.screen`, which no model can reach. Anything a model does
    here happens afterwards, to describe a decision that has already been made.
    """
    result = screen(trial.criteria_set, patient, as_of, policy=config.absence_policy)

    if config.write_rationales and trial.criteria_set.criteria:
        rationales = write_rationales(result, trial.criteria_set, ctx)
    else:
        rationales = deterministic_rationales(result)

    return Screening(trial=trial, result=result, rationales=rationales)
