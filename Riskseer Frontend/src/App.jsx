import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ??
  import.meta.env.VITE_API_BASE ??
  "http://127.0.0.1:8000";
const STATIC_DEMO = import.meta.env.VITE_STATIC_DEMO === "true";

function titleCaseFromEnum(value) {
  if (!value) return "Unknown";

  return String(value)
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatPercent(value) {
  const numeric = Number(value ?? 0);
  if (!Number.isFinite(numeric)) return "0%";
  return `${Math.round(numeric * 100)}%`;
}

function formatDateTime(value) {
  if (!value) return "Unknown";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function scoreTone(urgency) {
  if (urgency === "CRITICAL") return "critical";
  if (urgency === "HIGH") return "high";
  if (urgency === "MODERATE") return "moderate";
  return "low";
}

function getCaseTone(caseData) {
  if (caseData.status === "CLOSED") return "closed";
  if (caseData.status === "INACTIVE") return "inactive";
  return scoreTone(caseData.urgency);
}

function getEvidenceLayers(caseData) {
  const layers = caseData.evidence_layers || {};

  return {
    observed: Array.isArray(layers.observed) ? layers.observed : [],
    derived: Array.isArray(layers.derived) ? layers.derived : [],
    inferred: Array.isArray(layers.inferred) ? layers.inferred : [],
    assumed: Array.isArray(layers.assumed) ? layers.assumed : [],
  };
}

function getResponsibilityIntegrity(caseData) {
  return caseData.responsibility_integrity && typeof caseData.responsibility_integrity === "object"
    ? caseData.responsibility_integrity
    : {};
}

function getDecisionSupport(caseData) {
  return getResponsibilityIntegrity(caseData).decision_support_integrity || {};
}

function getResponsibilityLayers(caseData) {
  return getResponsibilityIntegrity(caseData).layers || {};
}

function getDecisionDefensibility(caseData) {
  return caseData.decision_defensibility && typeof caseData.decision_defensibility === "object"
    ? caseData.decision_defensibility
    : {};
}

function _getDefensibilityState(caseData) {
  return String(getDecisionDefensibility(caseData).state || "").toUpperCase();
}

function _getResponsibilityLayerState(caseData, key) {
  const layer = getResponsibilityLayers(caseData)[key];
  return String(layer?.state || "").toUpperCase();
}

function getResponsibilityState(caseData) {
  return String(getDecisionSupport(caseData).state || "").toUpperCase();
}

function hasDegradedResponsibilitySupport(caseData) {
  return ["PARTIAL", "DEGRADED", "CONFLICTED"].includes(getResponsibilityState(caseData));
}

function buildResponsibilityChainStory(caseData) {
  const rim = getResponsibilityIntegrity(caseData);
  const decisionSupport = getDecisionSupport(caseData);
  const layers = getResponsibilityLayers(caseData);
  const orderedKeys = ["excavator", "locate", "marks", "assets", "coordination"];
  const layerItems = orderedKeys
    .map((key) => {
      const layer = layers[key];
      if (!layer) return null;
      return {
        key,
        label:
          key === "excavator"
            ? "Excavator"
            : key === "locate"
            ? "Locate"
            : key === "marks"
            ? "Marks"
            : key === "assets"
            ? "Assets"
            : "Coordination",
        state: String(layer.state || "UNKNOWN").toUpperCase(),
        reason: layer.reason || "No layer reason returned.",
      };
    })
    .filter(Boolean);
  const weakLayer = layerItems.find((item) =>
    ["CONFLICTED", "MISSING", "UNKNOWN", "WEAK"].includes(item.state)
  );
  const supportState = String(decisionSupport.state || "UNKNOWN").toUpperCase();
  const decisionRisk = String(decisionSupport.decision_risk || "UNKNOWN").toUpperCase();
  const reason =
    decisionSupport.reason ||
    caseData.operator_summary ||
    "Responsibility-chain support has not been summarized by the backend.";
  const command =
    caseData.status === "CLOSED"
      ? "Reference only"
      : caseData.status === "INACTIVE"
      ? "Watch for return"
      : caseData.response_posture === "HOLD_WORK"
      ? "Stop work"
      : caseData.response_posture === "ESCALATE"
      ? "Escalate"
      : caseData.response_posture === "VERIFY_BEFORE_PROCEEDING"
      ? "Verify first"
      : caseData.response_posture === "VERIFY"
      ? "Verify"
      : hasDegradedResponsibilitySupport(caseData)
      ? "Monitor support"
      : "Monitor";

  return {
    supportState,
    decisionRisk,
    reason,
    command,
    layerItems,
    weakLayer,
    propagation: Array.isArray(rim.failure_propagation) ? rim.failure_propagation : [],
  };
}

function toStatements(items, fallback = []) {
  const statements = (items || [])
    .map((item) => item?.statement || item?.summary || item)
    .filter(Boolean);

  return statements.length > 0 ? statements : fallback;
}

function buildContradiction(caseData) {
  const chain = buildResponsibilityChainStory(caseData);
  const evidence = getEvidenceLayers(caseData);
  const assumed = toStatements(evidence.assumed);
  const invalidators = [
    ...(caseData.why_now || []),
    ...toStatements(evidence.derived),
    ...toStatements(caseData.conflicts || []),
  ].filter(Boolean);
  const alignment = caseData.alignment_assessment || {};
  const spatial = Number(alignment.spatial_alignment);
  const temporal = Number(alignment.temporal_alignment);
  const hasStrongTicketSupport =
    caseData.ticket_ids?.length &&
    Number.isFinite(spatial) &&
    Number.isFinite(temporal) &&
    spatial >= 0.8 &&
    temporal >= 0.8;
  const hasAnyTicketSupport = caseData.ticket_ids?.length;

  const belief =
    assumed[0] ||
    (hasStrongTicketSupport
      ? "work appears covered because ticket timing and area still line up"
      : hasAnyTicketSupport
      ? "work appears covered because one or more tickets exist"
      : "the current operating picture is good enough to proceed");

  const invalidation =
    invalidators[0] ||
    caseData.operator_summary ||
    "the available evidence does not justify passive trust";

  if (caseData.status === "CLOSED") {
    return {
      belief,
      invalidation,
      statement:
        "This case is closed. Keep it as history only unless new matching field activity brings it back to life.",
    };
  }

  if (caseData.status === "INACTIVE") {
    return {
      belief,
      invalidation,
      statement:
        "This case is inactive. Nothing live is forcing an interruption right now, but it should come back into focus if matching activity returns.",
    };
  }

  if (caseData.response_posture === "MONITOR") {
    return {
      belief,
      invalidation: chain.reason || invalidation,
      statement:
        chain.supportState === "SUPPORTED"
          ? "This case is supported enough to monitor without interrupting, while staying visible for changes."
          : "This case is not being interrupted, but its responsibility chain is not fully strong. Keep it visible and watch the weak layer.",
    };
  }

  return {
    belief,
    invalidation: chain.reason || invalidation,
    statement: `You think ${belief.charAt(0).toLowerCase()}${belief.slice(
      1
    )}. This assumption is likely wrong because ${invalidation.charAt(0).toLowerCase()}${invalidation.slice(
      1
    )}.`,
  };
}

function buildContradictionMeta(caseData) {
  if (caseData.status === "CLOSED") {
    return {
      eyebrow: "Historical Context",
      title: "Why this stays on record",
      beliefTitle: "What looked normal",
      breaksTitle: "Why it was kept",
      changedTitle: "What changed",
    };
  }

  if (caseData.status === "INACTIVE") {
    return {
      eyebrow: "Watch Context",
      title: "Why this is inactive",
      beliefTitle: "What looked normal",
      breaksTitle: "What would bring it back",
      changedTitle: "What changed",
    };
  }

  if (caseData.response_posture === "MONITOR") {
    return {
      eyebrow: "Watch Context",
      title: "Why this is not being interrupted",
      beliefTitle: "What looks normal",
      breaksTitle: "What could change",
      changedTitle: "What changed",
    };
  }

  return {
    eyebrow: "Contradiction",
    title: "What the crew thinks vs what breaks it",
    beliefTitle: "What they believe",
    breaksTitle: "Why proceed is not justified",
    changedTitle: "What changed",
  };
}

function buildDecisionPunchline(caseData) {
  const chain = buildResponsibilityChainStory(caseData);
  if (hasDegradedResponsibilitySupport(caseData) && chain.reason) {
    return chain.reason;
  }

  if (caseData.ui_summary?.reason) {
    return caseData.ui_summary.reason;
  }

  if (caseData.status === "CLOSED") {
    return "This case is closed and kept for reference only.";
  }

  if (caseData.status === "INACTIVE") {
    return "This is not live right now, but it could matter again if activity returns.";
  }

  if (caseData.response_posture === "HOLD_WORK") {
    return "The current support is too weak to keep working without a pause.";
  }

  if (caseData.response_posture === "ESCALATE") {
    return "Current support is weak enough that a human review should step in now.";
  }

  if (caseData.response_posture === "VERIFY_BEFORE_PROCEEDING") {
    return "This still might be fine, but not without checking what no longer lines up.";
  }

  if (caseData.response_posture === "MONITOR") {
    return chain.supportState === "SUPPORTED"
      ? "Decision support is coherent enough to monitor without interrupting."
      : "Do not interrupt yet, but the responsibility chain is not fully strong.";
  }

  return "The reason this work looks valid is weaker than it appears.";
}

function buildDamageLine(caseData) {
  const chain = buildResponsibilityChainStory(caseData);
  if (caseData.ui_summary?.consequence) {
    return `Consequence: ${caseData.ui_summary.consequence}`;
  }

  if (caseData.response_posture === "MONITOR") {
    return chain.weakLayer
      ? `Watch for: ${chain.weakLayer.label.toLowerCase()} support is ${titleCaseFromEnum(chain.weakLayer.state).toLowerCase()}.`
      : "Watch for: support could weaken if scope, timing, or activity changes.";
  }

  if (caseData.status === "CLOSED") {
    return "Consequence: this matters only if similar activity returns later.";
  }

  if (caseData.status === "INACTIVE") {
    return "Consequence: this comes back into focus only if matching activity resumes.";
  }

  return "Consequence: the crew could keep moving on support that does not hold up.";
}

function buildEscalationSummary(caseData) {
  if (caseData.ui_summary?.action) {
    return caseData.ui_summary.action;
  }

  if (caseData.status === "CLOSED") {
    return "Keep for reference only unless matching field activity returns.";
  }

  if (caseData.status === "INACTIVE") {
    return "Hold off for now and reopen this only if matching activity returns.";
  }

  if (caseData.response_posture === "HOLD_WORK") {
    return "Pause work before continuing.";
  }

  if (caseData.response_posture === "ESCALATE") {
    return "Interrupt and escalate for human review.";
  }

  if (caseData.response_posture === "VERIFY_BEFORE_PROCEEDING") {
    return "Verify before continuing.";
  }

  if (hasDegradedResponsibilitySupport(caseData)) {
    return "Monitor, but keep the responsibility-chain weakness visible.";
  }
  return "Monitor for changes in scope, timing, or support.";
}

function buildWeakSupportList(caseData) {
  const chain = buildResponsibilityChainStory(caseData);
  if (caseData.status === "CLOSED") {
    return [
      "No fresh matching activity kept this thread live.",
      "It stays useful as history if similar work appears again.",
    ];
  }

  if (caseData.status === "INACTIVE") {
    return [
      "The continuity gap is too large to treat this as live work.",
      "Fresh matching activity would move it back into live review.",
    ];
  }

  if (caseData.response_posture === "MONITOR") {
    if (chain.weakLayer) {
      return [
        `${chain.weakLayer.label} support is ${titleCaseFromEnum(chain.weakLayer.state).toLowerCase()}.`,
        chain.weakLayer.reason,
      ];
    }
    return [
      "Responsibility support is coherent enough to monitor right now.",
      "Any new conflict, scope drift, or repetition should move this back into review.",
    ];
  }

  const items = [];
  const whyNow = caseData.why_now || [];

  if (whyNow.some((item) => /no plausible matching ticket/i.test(item || ""))) {
    items.push("No clear active ticket matches this exact location and time.");
  }
  if (whyNow.some((item) => /overlapping ticket|conflicts across/i.test(item || ""))) {
    items.push("Multiple tickets point in different directions.");
  }
  if (whyNow.some((item) => /outside.*window|expired|time coverage conflicts/i.test(item || ""))) {
    items.push("Ticket timing does not line up cleanly with current activity.");
  }
  if (whyNow.some((item) => /outside.*area|scope conflict/i.test(item || ""))) {
    items.push("The work area does not line up cleanly with the available ticket context.");
  }
  if (hasConcern(caseData, /continuing|repeated|habit/i)) {
    items.push("Work is still moving as if the support is already settled.");
  }

  return [...new Set(items)].slice(0, 3);
}

function buildSupportStatus(caseData) {
  const chain = buildResponsibilityChainStory(caseData);
  if (chain.supportState && chain.supportState !== "UNKNOWN") {
    return {
      label: "Chain support",
      value: titleCaseFromEnum(chain.supportState),
      detail: chain.reason,
    };
  }

  const weakItems = buildWeakSupportList(caseData);

  if (weakItems.length === 0) {
    return {
      label: "Support status",
      value: "Stable enough",
      detail: "Nothing obvious is missing, conflicting, or incomplete right now.",
    };
  }

  return {
    label: "Support status",
    value: weakItems[0],
    detail: weakItems.slice(1).join(" ") || "Support is weaker or messier than it looks.",
  };
}

function buildAuthorizationClarity(caseData) {
  const whyNow = caseData.why_now || [];
  const alignment = caseData.alignment_assessment || {};
  const mixedSignals = whyNow.some((item) =>
    /conflicts across|unresolved|ambiguity|ambiguous|no plausible matching ticket/i.test(
      item || ""
    )
  );
  const partialAlignment =
    Number(alignment.spatial_alignment ?? 1) < 0.65 ||
    Number(alignment.temporal_alignment ?? 1) < 0.65;

  if (mixedSignals || partialAlignment) {
    return {
      label: "LOW",
      detail: "Overlapping or partial ticket context is weakening authorization clarity",
    };
  }

  if (Number(alignment.ticket_match_strength ?? 0) < 0.8) {
    return {
      label: "MEDIUM",
      detail: "Authorization context is usable, but not cleanly aligned",
    };
  }

  return {
    label: "HIGH",
    detail: "Authorization context appears cleanly aligned",
  };
}

function buildPrimaryRisk(caseData) {
  const behavioralConcerns = caseData.behavioral_risk_assessment?.concerns || [];
  const behavioralSummary = caseData.behavioral_risk_assessment?.summary || "";
  const whyNow = caseData.why_now || [];
  const candidate = [
    ...whyNow,
    ...behavioralConcerns,
    behavioralSummary,
  ].find((item) => /continuing|unresolved authorization|habit/i.test(item || ""));

  if (caseData.response_posture === "MONITOR") {
    return "Nothing here is strong enough to interrupt yet, but that can change fast.";
  }

  return (
    candidate ||
    "This could keep moving even though the crew has less support than it seems"
  );
}

function hasConcern(caseData, pattern) {
  const sources = [
    ...(caseData.why_now || []),
    ...(caseData.behavioral_risk_assessment?.concerns || []),
    ...(caseData.information_integrity_assessment?.concerns || []),
    ...(caseData.alignment_assessment?.concerns || []),
  ];

  return sources.some((item) => pattern.test(item || ""));
}

function buildPatternFrame(caseData) {
  if (hasConcern(caseData, /continuing|repeated|habit/i)) {
    return "Work is still moving even though the ticket story is not settled.";
  }

  if (hasConcern(caseData, /conflict|ambigu|partial/i)) {
    return "It looks covered at a glance, but the ticket coverage does not line up cleanly.";
  }

  return "It looks routine right now, but the support for continuing is thinner than it seems.";
}

function buildConsequenceFrame(caseData) {
  const heavy = hasConcern(caseData, /mechanized|heavy equipment/i);
  const trenchless = hasConcern(caseData, /reduced-visibility|trenchless|hdd|boring/i);
  const nearAsset = getEvidenceLayers(caseData).observed.some((item) =>
    /near one or more mapped assets/i.test(item?.statement || "")
  );

  if ((heavy || trenchless) && nearAsset) {
    return "High chance of damage before visible warning.";
  }

  if (heavy) {
    return "Mechanized work can turn weak decision support into damage quickly.";
  }

  if (nearAsset) {
    return "Nearby asset exposure makes the downside higher than the cost of a short stop.";
  }

  return "A quick check costs less than finding out too late that the crew leaned on a weak assumption.";
}

function buildInterruptionWorth(caseData) {
  if (caseData.status === "CLOSED") {
    return {
      label: "HISTORY ONLY",
      detail: "Historical only. Keep for reference, not live interruption.",
      threshold: "Not a live stop condition.",
    };
  }

  if (caseData.status === "INACTIVE") {
    return {
      label: "WAIT FOR REACTIVATION",
      detail: "Wait for activity to resume before interrupting the crew.",
      threshold: "Not a live stop condition yet.",
    };
  }

  if (caseData.response_posture === "HOLD_WORK") {
    return {
      label: "STOP REQUIRED",
      detail: "This may look normal, but there is not enough support to keep working.",
      threshold: "Work is still moving while the support for it is unresolved.",
    };
  }

  if (caseData.response_posture === "ESCALATE") {
    return {
      label: "INTERRUPT AND ESCALATE",
      detail: "This needs a person to step in before the crew leans on a weak call.",
      threshold: "There is enough drift here to break routine and get a review.",
    };
  }

  if (caseData.response_posture === "VERIFY_BEFORE_PROCEEDING") {
    return {
      label: "VERIFY BEFORE CONTINUING",
      detail: "This still might be fine, but not without checking what no longer lines up.",
      threshold: "Not a full stop, but enough drift to pause and verify.",
    };
  }

  return {
    label: "PROCEED",
    detail: "Do not slow the crew right now. Nothing here is strong enough to justify a stop or pause.",
    threshold: "Looks stable enough to keep moving, but stay alert for change.",
  };
}

function buildOperatorBelief(caseData) {
  const evidence = getEvidenceLayers(caseData);
  const assumed = toStatements(evidence.assumed);
  const observed = (caseData.observations || []).map((item) => item.summary).filter(Boolean);
  const preconditions = [
    ...assumed,
    ...observed.filter((statement) =>
      /inside|ticket|observed|asset/i.test(statement || "")
    ),
  ];

  return [...new Set(preconditions)].slice(0, 4);
}

function buildRealityBreaks(caseData) {
  if (caseData.status === "CLOSED") {
    return [
      "No fresh matching activity is keeping this thread live.",
      "It stays on record in case the same pattern shows up again.",
    ];
  }

  if (caseData.status === "INACTIVE") {
    return [
      "No current field activity is forcing an interruption right now.",
      "Fresh matching activity would put this back into live review.",
    ];
  }

  if (caseData.response_posture === "MONITOR") {
    return [
      "Site conditions can change fast even when the work still looks routine.",
      "Any new conflict, repetition, or scope drift should move this back into review.",
    ];
  }

  const evidence = getEvidenceLayers(caseData);
  const breaks = [
    ...(caseData.why_now || []),
    ...toStatements(evidence.derived),
    ...(caseData.information_integrity_assessment?.concerns || []),
    ...(caseData.alignment_assessment?.concerns || []),
  ].filter(Boolean);

  return [...new Set(breaks)].slice(0, 5);
}

function buildActionList(caseData) {
  if (caseData.response_posture === "HOLD_WORK") {
    return [
      "Confirm ticket coverage for this exact location and time.",
      "Verify the current work scope still matches the ticket.",
      "Re-check markings against the active work area.",
    ];
  }

  if (caseData.response_posture === "ESCALATE") {
    return [
      "Get a human review before the crew keeps moving.",
      "Confirm ticket coverage for this exact location and time.",
      "Verify the current work scope still matches the ticket.",
    ];
  }

  if (caseData.response_posture === "VERIFY_BEFORE_PROCEEDING") {
    return [
      "Confirm ticket coverage for this exact location and time.",
      "Verify the current work scope still matches the ticket.",
      "Re-check markings against current activity.",
    ];
  }

  const actions = Array.isArray(caseData.recommended_actions)
    ? caseData.recommended_actions
    : [];

  if (actions.length > 0) return actions.slice(0, 3);

  return ["Keep work moving, but watch for changes in timing, location, or ticket support."];
}

function buildSpotlightLooksNormal(caseData) {
  const items = [];

  if ((caseData.ticket_ids || []).length > 0) {
    items.push("A ticket exists for this area.");
  }

  items.push("The work can still look routine to the crew.");
  items.push("Nothing in the current feed guarantees the problem would be obvious on sight.");

  return [...new Set(items)].slice(0, 3);
}

function _buildSpotlightWeakPoints(caseData) {
  const whyNow = caseData.why_now || [];
  const weakPoints = [];

  if (whyNow.some((item) => /without a plausible matching ticket/i.test(item || ""))) {
    weakPoints.push("No active ticket clearly covers this exact location and time.");
  }
  if (whyNow.some((item) => /conflicts across overlapping ticket areas/i.test(item || ""))) {
    weakPoints.push("Ticket area coverage does not line up cleanly with current activity.");
  }
  if (whyNow.some((item) => /candidate tickets|timing does not support confidence|time coverage conflicts/i.test(item || ""))) {
    weakPoints.push("Ticket timing does not line up cleanly with current activity.");
  }
  if (whyNow.some((item) => /intended area|spatial scope/i.test(item || ""))) {
    weakPoints.push("Current work cannot be cleanly tied to the intended ticket area.");
  }
  if ((caseData.behavioral_risk_assessment?.concerns || []).some((item) => /continu|repeat|habit/i.test(item || ""))) {
    weakPoints.push("Work is still moving as if coverage is certain.");
  }
  if ((caseData.behavioral_risk_assessment?.concerns || []).some((item) => /mechanized|heavy/i.test(item || ""))) {
    weakPoints.push("Machine work raises the downside if that trust is misplaced.");
  }
  if (weakPoints.length === 0) {
    weakPoints.push("The support for continuing is thinner than it first appears.");
  }

  return [...new Set(weakPoints)].slice(0, 4);
}

function _buildSpotlightChecks(caseData) {
  const checks = [];

  if ((caseData.ticket_ids || []).length > 0) {
    checks.push("Confirm the active ticket really covers this exact location and time.");
  } else {
    checks.push("Confirm whether any active ticket actually covers this exact location and time.");
  }

  checks.push("Confirm the current work scope matches what was requested.");
  checks.push("Confirm markings or other field validation still line up with current activity.");

  return checks.slice(0, 3);
}

function _buildSpotlightWhyMatters(caseData) {
  const heavy = (caseData.behavioral_risk_assessment?.concerns || []).some((item) =>
    /mechanized|heavy/i.test(item || "")
  );

  if ((caseData.ticket_ids || []).length > 0) {
    return heavy
      ? "A ticket can make this look covered even when the area, timing, or scope no longer line up. If machine work keeps moving on that assumption, the downside rises fast."
      : "A ticket can make this look covered even when the area, timing, or scope no longer line up cleanly.";
  }

  return heavy
    ? "Crews can keep moving because the work still looks ordinary. Without clean support, machine work can turn that false confidence into damage fast."
    : "Crews can keep moving because the work still looks ordinary even when the support behind it has gotten weak.";
}

function describeSupportStrength(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return { value: "Unknown", detail: "not enough signal" };
  }
  if (numeric <= 0.15) {
    return { value: "None", detail: "not supported" };
  }
  if (numeric < 0.5) {
    return { value: "Weak", detail: "does not line up cleanly" };
  }
  if (numeric < 0.8) {
    return { value: "Partial", detail: "mixed support" };
  }
  return { value: "Strong", detail: "lines up cleanly" };
}

function _buildMissabilityReasons(caseData) {
  const reasons = [];
  const ticketCount = getRelevantTicketCount(caseData);
  const whyNow = caseData.why_now || [];
  const alignment = caseData.alignment_assessment || {};
  const heavy = hasConcern(caseData, /mechanized|heavy equipment/i);

  if (
    whyNow.some((item) => /without a plausible matching ticket/i.test(item || ""))
  ) {
    reasons.push(
      "There is no active ticket, but the work could still look routine because nothing on site guarantees the gap would be obvious at a glance."
    );
  }

  if (ticketCount > 1) {
    reasons.push(
      "More than one ticket is in play, so this can still look covered before anyone checks which one really supports the work."
    );
  } else if (ticketCount === 1) {
    reasons.push(
      "A ticket exists, so the work can look covered even if the support behind it is getting weaker."
    );
  }

  if (
    Number.isFinite(Number(alignment.spatial_alignment)) &&
    Number.isFinite(Number(alignment.temporal_alignment))
  ) {
    const spatial = Number(alignment.spatial_alignment);
    const temporal = Number(alignment.temporal_alignment);
    if (spatial >= 0.75 && temporal < 0.75) {
      reasons.push(
        "The area can look close enough while timing support is weak, which makes the situation easier to wave through."
      );
    } else if (temporal >= 0.75 && spatial < 0.75) {
      reasons.push(
        "Timing can look fine even though the work area does not line up cleanly, which can hide the break at a glance."
      );
    }
  }

  if ((caseData.behavioral_risk_assessment?.concerns || []).some((item) => /continu|repeat|habit/i.test(item || ""))) {
    reasons.push(
      "The work is still moving in a familiar pattern, which makes it easier to keep going on habit."
    );
  }

  if (heavy) {
    reasons.push(
      "The operation has escalated to machinery, but the surface story can still feel routine enough to pass without a harder check."
    );
  }

  if (reasons.length === 0) {
    reasons.push(
      "This still looks ordinary enough that someone could treat it as good enough without checking what support has weakened."
    );
  }

  return [...new Set(reasons)].slice(0, 3);
}

function getRelevantTicketCount(caseData) {
  return new Set([...(caseData.ticket_ids || []), ...(caseData.context_ticket_ids || [])].filter(Boolean))
    .size;
}

function getRelevantAssetCount(caseData) {
  return new Set([...(caseData.asset_ids || []), ...(caseData.context_asset_ids || [])].filter(Boolean))
    .size;
}

function buildDecisionConfidence(caseData) {
  if (caseData.ui_summary?.confidence?.level) {
    return {
      label: titleCaseFromEnum(caseData.ui_summary.confidence.level),
      detail: caseData.ui_summary.confidence.basis || "backend confidence basis not provided",
    };
  }

  if (caseData.response_posture === "MONITOR") {
    return {
      label: "High",
      detail: "current support is straightforward",
    };
  }

  if (caseData.response_posture === "HOLD_WORK") {
    return {
      label: "High",
      detail: "current support is too weak to rely on",
    };
  }

  if (caseData.response_posture === "ESCALATE" || caseData.response_posture === "VERIFY_BEFORE_PROCEEDING") {
    return {
      label: "Medium",
      detail: "support needs a human check before work continues",
    };
  }

  return {
    label: "Low",
    detail: "backend confidence basis not provided",
  };
}

function buildEvidenceSnapshot(caseData) {
  const chain = buildResponsibilityChainStory(caseData);
  const whyNow = caseData.why_now || [];
  const alignment = caseData.alignment_assessment || {};
  const ticketCount = getRelevantTicketCount(caseData);
  const assetCount = getRelevantAssetCount(caseData);
  const integrityConcerns = caseData.information_integrity_assessment?.concerns || [];
  const items = [];

  if (chain.supportState && chain.supportState !== "UNKNOWN") {
    items.push({
      label: "Chain support",
      value: titleCaseFromEnum(chain.supportState),
      detail:
        chain.weakLayer
          ? `${chain.weakLayer.label}: ${titleCaseFromEnum(chain.weakLayer.state)}`
          : titleCaseFromEnum(chain.decisionRisk),
    });
  }

  if (whyNow.some((item) => /no plausible matching ticket|without a plausible matching ticket/i.test(item || ""))) {
    items.push({ label: "Matching tickets", value: "0", detail: "none found" });
  } else if (
    whyNow.some((item) => /conflicts across overlapping ticket areas|overlapping ticket/i.test(item || ""))
  ) {
    items.push({
      label: "Matching tickets",
      value: String(ticketCount || 2),
      detail: "conflicting",
    });
  } else if (ticketCount > 0) {
    items.push({
      label: "Matching tickets",
      value: String(ticketCount),
      detail: ticketCount === 1 ? "supporting" : "in case context",
    });
  }

  if (Number.isFinite(Number(alignment.temporal_alignment))) {
    const support = describeSupportStrength(alignment.temporal_alignment);
    items.push({
      label: "Timing support",
      value: support.value,
      detail: support.detail,
    });
  }

  if (Number.isFinite(Number(alignment.spatial_alignment))) {
    const support = describeSupportStrength(alignment.spatial_alignment);
    items.push({
      label: "Area support",
      value: support.value,
      detail: support.detail,
    });
  }

  if (assetCount > 0) {
    items.push({
      label: "Mapped assets",
      value: String(assetCount),
      detail: "nearby",
    });
  }

  if (integrityConcerns.length > 0) {
    items.push({
      label: "Support gaps",
      value: String(integrityConcerns.length),
      detail: "open issues",
    });
  }

  if (items.length === 0) {
    items.push({
      label: "Support",
      value: "Stable",
      detail: "nothing obvious is breaking right now",
    });
  }

  return items.slice(0, 4);
}

function buildHiddenRiskAssessment(caseData) {
  const backendHiddenRisk =
    caseData.hidden_risk ||
    caseData.temporal_change?.hidden_risk ||
    null;
  const currentBackendHiddenRisk =
    backendHiddenRisk?.current && typeof backendHiddenRisk.current === "object"
      ? backendHiddenRisk.current
      : backendHiddenRisk && typeof backendHiddenRisk === "object"
      ? backendHiddenRisk
      : null;
  const priorBackendHiddenRisk =
    backendHiddenRisk?.prior && typeof backendHiddenRisk.prior === "object"
      ? backendHiddenRisk.prior
      : null;
  const hiddenRiskDelta = Number(
    backendHiddenRisk?.delta ??
      caseData.temporal_change?.hidden_risk?.delta ??
      0
  );

  const active = caseData.status === "ACTIVE";
  const posture = caseData.response_posture || "MONITOR";
  const ticketCount = getRelevantTicketCount(caseData);
  const weakSupport = buildWeakSupportList(caseData);
  const whyNow = caseData.why_now || [];
  const looksRoutine = buildSpotlightLooksNormal(caseData);
  const nearAsset = getRelevantAssetCount(caseData) > 0;
  const continuing = hasConcern(caseData, /continu|repeat|habit/i);
  const heavy = hasConcern(caseData, /mechanized|heavy equipment/i);
  const alignment = caseData.alignment_assessment || {};
  const hiddenBySurface = ticketCount > 0 || posture === "MONITOR";

  if (!active || posture === "HOLD_WORK") {
    return {
      eligible: false,
      score: 0,
      band: "low_missability",
      priorScore: Number(priorBackendHiddenRisk?.score || 0),
      delta: hiddenRiskDelta,
      components: currentBackendHiddenRisk?.components || {},
      title: "Not a hidden-risk candidate",
      detail: "Either not active or already obvious enough to force a stop.",
      reasons: [],
    };
  }

  if (currentBackendHiddenRisk) {
    const components = currentBackendHiddenRisk.components || {};
    const band = currentBackendHiddenRisk.band || "low_missability";
    const routineAppearance = Number(components.routine_appearance_score || 0);
    const supportWeakness = Number(components.support_weakness_score || 0);
    const consequence = Number(
      components.consequence_if_waved_through_score || 0
    );
    const interventionGap = Number(components.intervention_gap_score || 0);

    const reasons = [];
    if (routineAppearance >= 60) {
      if (ticketCount > 1) {
        reasons.push(
          `${ticketCount} tickets are present, so the work can look covered before anyone checks closely.`
        );
      } else if (ticketCount === 1) {
        reasons.push(
          "A ticket exists, so the work can look covered at a glance."
        );
      } else {
        reasons.push(
          "The work still looks routine enough that someone could wave it through."
        );
      }
    }
    if (supportWeakness >= 45) {
      const weakSupport = buildWeakSupportList(caseData);
      reasons.push(
        weakSupport[0] ||
          "Support underneath the routine appearance is weaker than it seems."
      );
    }
    if (consequence >= 35) {
      if (heavy) {
        reasons.push(
          "Machine work raises the downside if this gets waved through."
        );
      } else if (nearAsset) {
        reasons.push(
          "Nearby mapped assets raise the downside if this gets waved through."
        );
      } else {
        reasons.push(
          "The downside is meaningful if someone treats this as routine and keeps moving."
        );
      }
    }
    if (interventionGap >= 30 && reasons.length < 3) {
      reasons.push(
        posture === "MONITOR"
          ? "Nothing here is screaming, which is exactly why habit can glide past it."
          : "This still looks passable enough that someone might keep moving without a harder check."
      );
    }

    let title = "Hidden-risk candidate";
    let detail =
      "This still looks routine enough that someone could wave it through.";

    if (band === "most_missable") {
      title = "Most missable right now";
      detail =
        "This is the kind of active work that can look fine on the surface while support underneath it is weak.";
    } else if (band === "meaningful_candidate") {
      title = "Easy to wave through";
      detail =
        "It does not look alarming at a glance, but there is enough underneath it to deserve a harder look.";
    } else if (band === "worth_awareness") {
      title = "Worth a second look";
      detail =
        "This still looks mostly routine, but there is enough weak support here to keep visible.";
    } else if (band === "low_missability") {
      title = "Low missability concern";
      detail =
        "This is active, but it is not the best example of routine-looking weak support right now.";
    }

    return {
      eligible: Boolean(currentBackendHiddenRisk.eligible),
      score: Number(currentBackendHiddenRisk.score || 0),
      band,
      priorScore: Number(priorBackendHiddenRisk?.score || 0),
      delta: hiddenRiskDelta,
      components,
      title,
      detail,
      reasons: [...new Set(reasons)].slice(0, 3),
    };
  }

  let score = 0;

  if (posture === "ESCALATE") score += 60;
  else if (posture === "VERIFY_BEFORE_PROCEEDING") score += 48;
  else score += 34;

  if (hiddenBySurface) score += 20;
  if (ticketCount > 0) score += 12;
  if (continuing) score += 12;
  if (nearAsset) score += 8;
  score += Math.min(weakSupport.length * 6, 18);
  score += Math.min(looksRoutine.length * 4, 12);

  if (
    whyNow.some((item) =>
      /conflicts across overlapping ticket areas|overlapping ticket|outside.*window|time coverage conflicts|outside.*area|scope conflict/i.test(
        item || ""
      )
    )
  ) {
    score += 10;
  }

  const reasons = [];
  if (ticketCount > 0) {
    reasons.push(
      ticketCount === 1
        ? "A ticket exists, so the work can look covered at a glance."
        : `${ticketCount} tickets are in play, so this can still look covered before anyone checks closely.`
    );
  }
  if (
    Number.isFinite(Number(alignment.spatial_alignment)) &&
    Number.isFinite(Number(alignment.temporal_alignment)) &&
    Number(alignment.spatial_alignment) >= 0.75 &&
    Number(alignment.temporal_alignment) < 0.75
  ) {
    reasons.push(
      `Area support looks stronger (${formatPercent(alignment.spatial_alignment)}) than timing support (${formatPercent(
        alignment.temporal_alignment
      )}), which can hide the break at a glance.`
    );
  } else if (
    Number.isFinite(Number(alignment.temporal_alignment)) &&
    Number.isFinite(Number(alignment.spatial_alignment)) &&
    Number(alignment.temporal_alignment) >= 0.75 &&
    Number(alignment.spatial_alignment) < 0.75
  ) {
    reasons.push(
      `Timing looks stronger (${formatPercent(alignment.temporal_alignment)}) than area support (${formatPercent(
        alignment.spatial_alignment
      )}), so the work can still feel routine.`
    );
  }
  if (continuing) reasons.push("Work is still moving as if the support is settled.");
  if (heavy) reasons.push("The work has escalated to machinery, so a casual pass-through matters more.");
  else if (nearAsset) reasons.push("Nearby mapped assets raise the downside if this gets waved through.");
  if (weakSupport[0] && reasons.length < 3) reasons.push(weakSupport[0]);

  return {
    eligible: hiddenBySurface && (weakSupport.length > 0 || whyNow.length > 0),
    score: Math.min(100, score),
    band:
      Math.min(100, score) >= 80
        ? "most_missable"
        : Math.min(100, score) >= 60
        ? "meaningful_candidate"
        : Math.min(100, score) >= 30
        ? "worth_awareness"
        : "low_missability",
    priorScore: 0,
    delta: 0,
    components: {},
    title:
      posture === "MONITOR"
        ? "Routine-looking work that could get ignored"
        : "Weak support hiding behind normal-looking work",
    detail:
      posture === "MONITOR"
        ? "Nothing is screaming, but this is exactly the kind of case habit can glide past."
        : "This is risky because it still feels routine enough that someone could keep moving.",
    reasons: [...new Set(reasons)].slice(0, 3),
  };
}

function buildInformationGapAssessment(caseData) {
  const active = caseData.status === "ACTIVE";
  const whyNow = caseData.why_now || [];
  const infoConcerns = caseData.information_integrity_assessment?.concerns || [];
  const allSignals = [...whyNow, ...infoConcerns].filter(Boolean);
  const reasons = [];
  let score = 0;

  if (!active) {
    return {
      eligible: false,
      score: 0,
      title: "Not an active information-gap case",
      detail:
        "This layer is for live work where key support is missing, unclear, or still unknown.",
      reasons: [],
    };
  }

  if (
    allSignals.some((item) =>
      /no plausible matching ticket|without a plausible matching ticket/i.test(item || "")
    )
  ) {
    reasons.push("Ticket confirmation is missing for this exact location and time.");
    score += 45;
  }

  if (
    allSignals.some((item) =>
      /data gap|missing|incomplete|unknown|unclear|cannot confirm/i.test(item || "")
    )
  ) {
    reasons.push("Part of the support picture is missing, incomplete, or unknown.");
    score += 30;
  }

  if ((caseData.marking_ids || []).length === 0 && (caseData.asset_ids || []).length > 0) {
    reasons.push("No marking record is attached even though mapped assets are nearby.");
    score += 15;
  }

  if ((caseData.positive_response_ids || []).length === 0 && (caseData.ticket_ids || []).length > 0) {
    reasons.push("Ticket context exists here, but no positive response is attached.");
    score += 10;
  }

  if (
    allSignals.some((item) =>
      /weaker or messier|support is weak|support is thinner|not enough lines up/i.test(
        item || ""
      )
    )
  ) {
    reasons.push("The available support is too thin to trust at a glance.");
    score += 20;
  }

  return {
    eligible: reasons.length > 0,
    score: Math.min(100, score),
    title: "Key support is missing or unclear here",
    detail:
      "Part of the support picture is missing, unclear, or still unknown, so someone could keep moving without noticing what is absent.",
    reasons: [...new Set(reasons)].slice(0, 3),
  };
}

function buildConflictAssessment(caseData) {
  const active = caseData.status === "ACTIVE";
  const whyNow = caseData.why_now || [];
  const reasons = [];
  let score = 0;

  if (!active) {
    return {
      eligible: false,
      score: 0,
      title: "Not an active conflict case",
      detail:
        "This layer is for live work where support exists, but it does not agree with itself.",
      reasons: [],
    };
  }

  if (
    whyNow.some((item) =>
      /conflicts across overlapping ticket areas|outside.*area|intended area|spatial scope/i.test(
        item || ""
      )
    )
  ) {
    reasons.push("Ticket area support and current activity do not point to the same answer.");
    score += 35;
  }

  if (
    whyNow.some((item) =>
      /ticket time coverage conflicts|outside.*window|timing does not support confidence|expired/i.test(
        item || ""
      )
    )
  ) {
    reasons.push("Ticket timing support does not line up cleanly with current activity.");
    score += 35;
  }

  if ((caseData.ticket_ids || []).length > 1) {
    reasons.push("More than one ticket is in play for this work area.");
    score += 15;
  }

  if (hasConcern(caseData, /continuing|repeated|habit/i)) {
    reasons.push("Work is still moving even though the support story is conflicted.");
    score += 15;
  }

  return {
    eligible: reasons.length > 0,
    score: Math.min(100, score),
    title: "This looks covered, but the ticket story does not agree with itself",
    detail:
      "Support exists here, but it points in different directions, which is exactly how a routine-looking decision can go wrong.",
    reasons: [...new Set(reasons)].slice(0, 3),
  };
}

function buildEvidenceFeed(caseData) {
  const evidence = getEvidenceLayers(caseData);
  const ordered = [
    ...evidence.observed.map((item) => ({ ...item, lane: "Seen in data" })),
    ...evidence.derived.map((item) => ({ ...item, lane: "Signal" })),
    ...evidence.inferred.map((item) => ({ ...item, lane: "Pattern" })),
  ];

  return ordered.slice(0, 8);
}

function getLatestFieldEventTime(caseData) {
  const eventTimes = (caseData.attachments || [])
    .filter((attachment) => attachment?.record_type === "event")
    .map((attachment) => attachment?.metadata?.event_time || attachment?.attached_at)
    .map((value) => normalizeTimelineTime(value))
    .filter(Boolean)
    .map((date) => date.getTime());

  if (eventTimes.length === 0) return caseData.updated_at || null;
  return new Date(Math.max(...eventTimes)).toISOString();
}

function getLatestFieldEventMeta(caseData) {
  const eventAttachments = (caseData.attachments || [])
    .filter((attachment) => attachment?.record_type === "event")
    .map((attachment) => ({
      when: normalizeTimelineTime(attachment?.metadata?.event_time || attachment?.attached_at),
      metadata: attachment?.metadata || {},
    }))
    .filter((item) => item.when)
    .sort((left, right) => right.when.getTime() - left.when.getTime());

  if (eventAttachments.length > 0) {
    return eventAttachments[0].metadata || {};
  }

  const eventObservation = (caseData.observations || [])
    .filter((observation) => observation?.observation_type === "EVENT_SEEN")
    .map((observation) => ({
      when: normalizeTimelineTime(observation?.metadata?.event_time || caseData.updated_at),
      metadata: observation?.metadata || {},
    }))
    .filter((item) => item.when)
    .sort((left, right) => right.when.getTime() - left.when.getTime());

  return eventObservation[0]?.metadata || {};
}

function buildQueueLocation(caseData) {
  const metadata = getLatestFieldEventMeta(caseData);
  const lat = formatCoordinate(metadata.lat);
  const lon = formatCoordinate(metadata.lon);
  if (lat && lon) {
    return `Near ${lat}, ${lon}`;
  }
  if ((caseData.asset_ids || []).length > 0) {
    return `Near asset ${caseData.asset_ids[0]}`;
  }
  return "Location not pinned";
}

function buildQueueEvidenceLine(caseData) {
  const snapshots = caseData.evidenceSnapshot || [];
  const parts = [];

  const tickets = snapshots.find((item) => item.label === "Matching tickets");
  const timing = snapshots.find((item) => item.label === "Timing support");
  const area = snapshots.find((item) => item.label === "Area support");
  const assets = snapshots.find((item) => item.label === "Mapped assets");

  if (tickets) parts.push(`${tickets.value} tickets`);
  if (timing) parts.push(`Timing: ${timing.value}`);
  if (area) parts.push(`Area: ${area.value}`);
  if (assets) parts.push("Asset nearby");

  return parts.join(" | ");
}

function _buildQueueDecisionLine(caseData) {
  const chain = buildResponsibilityChainStory(caseData);
  const action = chain.command.toUpperCase();

  const reason = caseData.nowState?.decisionPunchline || caseData.queueReason;
  return `${action} - ${reason}`;
}

function _buildQueueActionHint(caseData) {
  if (caseData.ui_summary?.action) {
    const action = String(caseData.ui_summary.action).replace(/\.$/, "");
    if (caseData.response_posture === "HOLD_WORK") return `Stop - ${action.charAt(0).toLowerCase()}${action.slice(1)}`;
    if (caseData.response_posture === "ESCALATE") return `Escalate - ${action.charAt(0).toLowerCase()}${action.slice(1)}`;
    if (caseData.response_posture === "VERIFY_BEFORE_PROCEEDING") return `Verify - ${action.charAt(0).toLowerCase()}${action.slice(1)}`;
  }

  if (caseData.response_posture === "ESCALATE") {
    return "Escalate - get a human review before the crew keeps moving";
  }
  if (caseData.response_posture === "HOLD_WORK") {
    return "Stop - do not let the crew keep moving on this";
  }
  if (caseData.response_posture === "VERIFY_BEFORE_PROCEEDING") {
    return "Verify - check support before the crew keeps moving";
  }
  if (hasDegradedResponsibilitySupport(caseData)) {
    return "Monitor - chain support is not fully strong";
  }
  return "Monitor - still exposed if conditions change";
}

function _buildQueueActivityLabel(caseData) {
  if (caseData.status !== "ACTIVE") {
    return "Live activity: No";
  }

  const timestamp = new Date(caseData.lastFieldActivityAt || 0).getTime();
  if (!Number.isFinite(timestamp) || timestamp <= 0) {
    return "Live activity: Active case";
  }

  const minutesAgo = Math.round((Date.now() - timestamp) / 60000);
  if (minutesAgo <= 30) {
    return "Live activity: Likely ongoing";
  }
  if (minutesAgo <= 120) {
    return "Live activity: Recent";
  }
  return "Live activity: Active case";
}

function formatGapSummary(minutes) {
  const numeric = Number(minutes);
  if (!Number.isFinite(numeric) || numeric <= 0) return null;
  if (numeric >= 1440) {
    const days = Math.round((numeric / 1440) * 10) / 10;
    return `${days} day gap`;
  }
  if (numeric >= 60) {
    const hours = Math.round((numeric / 60) * 10) / 10;
    return `${hours} hour gap`;
  }
  return `${Math.round(numeric)} minute gap`;
}

function buildQueueSignals(caseData) {
  const chain = buildResponsibilityChainStory(caseData);
  const signals = [];
  const whyNow = caseData.why_now || [];
  const hasSignal = (pattern) => whyNow.some((item) => pattern.test(item || ""));

  if (hasSignal(/authorization context conflicts|ticket time coverage conflicts/i)) {
    signals.push("ticket context conflicts");
  }
  if (hasSignal(/without a plausible matching ticket/i)) {
    signals.push("no reliable ticket context");
  }
  if (hasSignal(/mechanized work/i)) {
    signals.push("mechanized consequence is higher");
  }
  if (hasSignal(/reduced-visibility/i)) {
    signals.push("reduced-visibility work leaves less recovery time");
  }
  if (hasSignal(/authorization remains unresolved|intensifying/i)) {
    signals.push("work is continuing under unresolved contradiction");
  }
  if ((caseData.information_integrity_assessment?.concerns || []).length > 0) {
    signals.push("the available picture is incomplete");
  }
  if (chain.weakLayer) {
    signals.push(`${chain.weakLayer.label.toLowerCase()} support is ${titleCaseFromEnum(chain.weakLayer.state).toLowerCase()}`);
  } else if (chain.supportState === "SUPPORTED") {
    signals.push("responsibility chain is supported enough to monitor");
  }

  if (caseData.response_posture === "MONITOR" && signals.length === 0) {
    const alignment = caseData.alignment_assessment || {};
    const eventCount = (caseData.event_ids || []).length;
    const strongArea = Number(alignment.spatial_alignment ?? 1) >= 0.85;
    const strongTime = Number(alignment.temporal_alignment ?? 1) >= 0.85;

    if ((caseData.ticket_ids || []).length > 0 && (caseData.asset_ids || []).length > 0 && strongArea && strongTime) {
      signals.push("activity remains near mapped assets, but ticket timing and area still line up");
    } else if ((caseData.ticket_ids || []).length > 0 && eventCount > 2 && strongArea) {
      signals.push("work has stayed inside the same supported area across multiple updates");
    } else if ((caseData.ticket_ids || []).length > 0 && strongTime) {
      signals.push("ticket timing and scope still line up with current activity");
    } else if ((caseData.ticket_ids || []).length > 0) {
      signals.push("ticket support remains in place with no new contradiction");
    } else if ((caseData.asset_ids || []).length > 0) {
      signals.push("activity is near mapped assets, but nothing new is weakening support");
    } else if (caseData.trendMeta?.value === "IMPROVING") {
      signals.push("recent updates are making the picture easier to trust");
    } else {
      signals.push("no recent changes are weakening decision confidence");
    }
  }

  return [...new Set(signals)].slice(0, 3);
}

function summarizeQueueReason(caseData) {
  const metadata = caseData.metadata || {};
  const gapSummary = formatGapSummary(
    metadata.last_status_transition?.gap_min ?? metadata.continuity_gap_min
  );
  const lastActivity = formatDateTime(getLatestFieldEventTime(caseData));
  const signals = buildQueueSignals(caseData);
  const chain = buildResponsibilityChainStory(caseData);
  const returnPriority = inferReturnPriority(caseData);

  if (caseData.status === "CLOSED") {
    return [
      "Reference only unless matching field activity returns.",
      `Last field activity seen ${lastActivity}.`,
      returnPriority.label
        ? `${returnPriority.label.charAt(0).toUpperCase()}${returnPriority.label.slice(1)}.`
        : null,
    ].join(" ");
  }

  if (caseData.status === "INACTIVE") {
    return [
      `${returnPriority.label.charAt(0).toUpperCase()}${returnPriority.label.slice(1)}.`,
      `Last field activity seen ${lastActivity}.`,
      gapSummary ? `It has been quiet for ${gapSummary}.` : null,
    ].join(" ");
  }

  if (signals.length > 0) {
    return `${signals[0].charAt(0).toUpperCase()}${signals[0].slice(1)}.`;
  }

  return chain.reason || buildContradiction(caseData).invalidation;
}

function formatLifecycleReason(value) {
  if (!value) return null;
  const text = String(value);
  const inactivityMatch = text.match(/inactive_for_more_than_(\d+)_minutes/i);
  if (inactivityMatch) {
    const minutes = Number(inactivityMatch[1]);
    const hours = Math.round((minutes / 60) * 10) / 10;
    return `No matching activity returned for more than ${hours} hours.`;
  }
  return titleCaseFromEnum(text);
}

function buildLifecycleContext(caseData) {
  const metadata = caseData.metadata || {};
  const transition = metadata.last_status_transition || {};
  const gapMinutes = Number(
    transition.gap_min ?? metadata.continuity_gap_min ?? metadata.reopen_gap_min
  );
  const gapText = Number.isFinite(gapMinutes)
    ? `${Math.round(gapMinutes)} minutes`
    : null;

  if (caseData.status === "CLOSED") {
    return {
      summary: "This case is closed because continuity dropped out long enough that it is no longer treated as live work.",
      whyClosed: [
        formatLifecycleReason(metadata.closure_reason) ||
          "No new related activity kept the case active.",
        gapText ? `The final continuity gap reached ${gapText}.` : null,
        transition?.at
          ? `The case moved from ${titleCaseFromEnum(transition.from)} to ${titleCaseFromEnum(transition.to)} on ${formatDateTime(transition.at)}.`
          : null,
      ].filter(Boolean),
      reactivation: [
        "A new event would reactivate this case if it matches the prior work thread closely enough on time, location, and context.",
        metadata.reopen_event_id
          ? `The last reopen candidate recorded by the backend was event ${metadata.reopen_event_id}.`
          : "A matching new field event is the normal reactivation trigger.",
      ],
    };
  }

  if (caseData.status === "INACTIVE") {
    return {
      summary: "This case is inactive because the contradiction still matters, but current continuity is too weak to treat it as live interruption.",
      whyClosed: [
        gapText ? `The latest continuity gap is ${gapText}.` : null,
        transition?.at
          ? `The case moved from ${titleCaseFromEnum(transition.from)} to ${titleCaseFromEnum(transition.to)} on ${formatDateTime(transition.at)}.`
          : "Recent activity was not strong enough to keep the case active.",
      ].filter(Boolean),
      reactivation: [
        "It will reactivate if a new event reconnects this work thread with strong enough spatial, temporal, and context continuity.",
        "Practically, that means fresh field activity near the same work area, assets, or ticket context.",
      ],
    };
  }

  return {
    summary: "This case is active because continuity is still strong enough to treat the current work thread as live.",
    whyClosed: [
      "New or continuing field activity is still matching this case closely enough to keep it active.",
    ],
    reactivation: [],
  };
}

function getCaseRelationIds(caseData) {
  return [
    ...(caseData.related_case_ids || []),
    ...(caseData.sibling_case_ids || []),
    ...(caseData.parent_case_id ? [caseData.parent_case_id] : []),
    ...(caseData.forked_from_case_id ? [caseData.forked_from_case_id] : []),
  ].filter(Boolean);
}

function matchesFilters(caseData, filters) {
  const search = filters.search.trim().toLowerCase();
  if (search) {
    const haystack = [
      caseData.case_id,
      ...(caseData.event_ids || []),
      ...(caseData.ticket_ids || []),
      ...(caseData.asset_ids || []),
      caseData.operator_summary,
      caseData.branch_reason,
      ...(caseData.related_case_ids || []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    if (!haystack.includes(search)) return false;
  }

  if (filters.status !== "ALL" && caseData.status !== filters.status) return false;
  if (filters.posture !== "ALL" && caseData.response_posture !== filters.posture) return false;
  if (filters.urgency !== "ALL" && caseData.urgency !== filters.urgency) return false;
  if (filters.trend !== "ALL" && caseData.trendMeta?.value !== filters.trend) return false;
  if (
    filters.failureLayer !== "ALL" &&
    caseData.primary_failure_layer !== filters.failureLayer
  ) {
    return false;
  }
  if (filters.relatedOnly && getCaseRelationIds(caseData).length === 0) return false;
  return true;
}

function normalizeTimelineTime(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date;
}

function describeAttachmentReason(reason, role) {
  const normalized = String(reason || "").trim().toUpperCase();

  if (role === "trigger") return "This event started the case thread";
  if (normalized === "CONTINUITY_PRESERVED_ACROSS_PRIMARY_AXES") {
    return "Matched the same case on location and timing";
  }
  if (normalized === "SHARED_IDENTITY_WITH_SPATIAL_DRIFT") {
    return "Started a related case because the work drifted away from the earlier footprint";
  }
  if (normalized === "CONTINUITY_SUPPORTED_UNDER_DEGRADED_PRIMARY_EVIDENCE") {
    return "Matched the case, but with weaker support than normal";
  }
  if (normalized === "CASE_ANCHOR_OR_INITIAL_ATTACHMENT") {
    return "Used as an early anchor for the case";
  }
  if (normalized === "NEW_CASE_ANCHOR") {
    return "Created a new case from this event";
  }

  return titleCaseFromEnum(reason || "attached_to_case");
}

function formatCoordinate(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return numeric.toFixed(5);
}

function buildEventNarrative(eventId, relatedObservations) {
  const baseObservation = relatedObservations.find(
    (observation) => observation?.observation_type === "EVENT_SEEN"
  );
  const baseMetadata = baseObservation?.metadata || {};

  const lat = formatCoordinate(baseMetadata.lat);
  const lon = formatCoordinate(baseMetadata.lon);
  const equipment = baseMetadata.equipment_type || baseObservation?.value;

  const insideTickets = relatedObservations
    .filter((observation) => observation?.observation_type === "INSIDE_TICKET_AREA")
    .map((observation) => observation?.ticket_id)
    .filter(Boolean);
  const outsideTickets = relatedObservations
    .filter(
      (observation) =>
        observation?.observation_type === "OUTSIDE_TICKET_AREA" ||
        observation?.observation_type === "OUTSIDE_TICKET_WINDOW"
    )
    .map((observation) => observation?.ticket_id)
    .filter(Boolean);
  const nearbyAssets = relatedObservations
    .filter((observation) => observation?.observation_type === "NEAR_ASSET")
    .map((observation) => observation?.asset_id)
    .filter(Boolean);

  const narrativeBits = [
    equipment ? `Activity looked like ${String(equipment).toLowerCase()}` : null,
    lat && lon ? `near ${lat}, ${lon}` : null,
    insideTickets.length > 0
      ? `inside ticket area ${[...new Set(insideTickets)].join(", ")}`
      : null,
    outsideTickets.length > 0
      ? `but conflicting with ${[...new Set(outsideTickets)].join(", ")}`
      : null,
    nearbyAssets.length > 0
      ? `near asset ${[...new Set(nearbyAssets)].join(", ")}`
      : null,
  ].filter(Boolean);

  if (narrativeBits.length === 0) {
    return `Event ${eventId} was observed and attached to this case.`;
  }

  return `${narrativeBits.join(", ")}.`;
}

function buildTimeline(caseData) {
  const items = [];
  const seen = new Set();
  const metadata = caseData.metadata || {};

  function pushItem(item) {
    const key = [
      item.kind,
      item.label,
      item.when || "",
      item.recordId || "",
    ].join("|");

    if (seen.has(key)) return;
    seen.add(key);
    items.push(item);
  }

  pushItem({
    kind: "case",
    label: "Case created",
    when: caseData.created_at,
    summary: `Case ${caseData.case_id} entered the registry.`,
    detail: caseData.parent_case_id
      ? `Created as a branch from case ${caseData.parent_case_id}.`
      : "Created as a new case thread.",
  });

  const eventObservations = new Map();
  for (const observation of caseData.observations || []) {
    const eventId = observation?.event_id;
    if (!eventId) continue;
    const bucket = eventObservations.get(eventId) || [];
    bucket.push(observation);
    eventObservations.set(eventId, bucket);
  }

  for (const attachment of caseData.attachments || []) {
    const sourceTime = attachment?.metadata?.event_time || attachment?.attached_at;
    const recordType = titleCaseFromEnum(attachment?.record_type);
    const role = attachment?.role ? titleCaseFromEnum(attachment.role) : "Attachment";
    const reason = describeAttachmentReason(
      attachment?.assessment?.reason,
      attachment?.role
    );

    if (attachment?.record_type === "event") {
      const relatedObservations = eventObservations.get(attachment?.record_id) || [];
      const observationHighlights = relatedObservations
        .filter((observation) => observation?.observation_type !== "EVENT_SEEN")
        .map((observation) => observation?.summary)
        .filter(Boolean)
        .slice(0, 4);

      pushItem({
        kind: "event",
        label: `Event ${attachment?.record_id}`,
        when: sourceTime,
        recordId: attachment?.record_id,
        metadata: attachment?.metadata || {},
        summary: buildEventNarrative(attachment?.record_id, relatedObservations),
        detail: [
          relatedObservations.find((observation) => observation?.observation_type === "EVENT_SEEN")
            ?.summary || null,
          `${reason}.`,
          attachment?.attached_at && attachment?.attached_at !== sourceTime
            ? `Linked to this case at ${formatDateTime(attachment.attached_at)}.`
            : null,
          observationHighlights.length > 0
            ? `What it triggered: ${observationHighlights.join(" | ")}.`
            : null,
        ]
          .filter(Boolean)
          .join(" "),
      });

      continue;
    }

    pushItem({
      kind: "attachment",
      label: `${recordType} attached`,
      when: sourceTime,
      recordId: attachment?.record_id,
      metadata: attachment?.metadata || {},
      summary: `${recordType} ${attachment?.record_id || ""} joined the case as ${role.toLowerCase()}.`.trim(),
      detail: [
        `${reason}.`,
        attachment?.attached_at && attachment?.attached_at !== sourceTime
          ? `Linked to this case at ${formatDateTime(attachment.attached_at)}.`
          : null,
      ]
        .filter(Boolean)
        .join(" "),
    });
  }

  for (const observation of caseData.observations || []) {
    if (observation?.event_id) continue;
    const observationTime = observation?.metadata?.event_time || caseData.updated_at;
    pushItem({
      kind: "observation",
      label: titleCaseFromEnum(observation?.observation_type),
      when: observationTime,
      recordId: observation?.event_id || observation?.ticket_id || observation?.asset_id || "",
      metadata: observation?.metadata || {},
      summary: observation?.summary || titleCaseFromEnum(observation?.observation_type),
      detail: "Observed as part of case evaluation.",
    });
  }

  const statusTransition = metadata.last_status_transition;
  if (statusTransition?.at) {
    pushItem({
      kind: "status",
      label: "Status changed",
      when: statusTransition.at,
      summary: `Case moved from ${titleCaseFromEnum(statusTransition.from)} to ${titleCaseFromEnum(statusTransition.to)}.`,
      detail:
        typeof statusTransition.gap_min === "number"
          ? `The continuity gap at transition was ${Math.round(statusTransition.gap_min)} minutes.`
          : "Lifecycle status changed based on continuity.",
    });
  }

  if (metadata.reopened_at) {
    pushItem({
      kind: "status",
      label: "Case reopened",
      when: metadata.reopened_at,
      summary: "New continuity evidence reactivated the case.",
      detail: metadata.reopen_event_id
        ? `Reopened because event ${metadata.reopen_event_id} matched the prior thread.`
        : "Reopened after new related field activity appeared.",
    });
  }

  if (metadata.closed_at) {
    pushItem({
      kind: "status",
      label: "Case closed",
      when: metadata.closed_at,
      summary: "The case aged out of active continuity and moved to closed history.",
      detail: metadata.closure_reason
        ? titleCaseFromEnum(metadata.closure_reason)
        : "No active continuity remained.",
    });
  }

  pushItem({
    kind: "evaluation",
    label: "Current evaluation",
    when: caseData.updated_at,
    summary: `${titleCaseFromEnum(caseData.decision_state)} with ${titleCaseFromEnum(caseData.response_posture)} posture.`,
    detail: caseData.operator_summary || "Current operator-facing summary.",
  });

  return items
    .map((item) => ({
      ...item,
      sortDate: normalizeTimelineTime(item.when),
    }))
    .sort((left, right) => {
      const leftTime = left.sortDate?.getTime() ?? 0;
      const rightTime = right.sortDate?.getTime() ?? 0;
      return leftTime - rightTime;
    });
}

function describeTimelineTimestamp(item) {
  const metadata = item.metadata || {};
  const label =
    metadata.timestamp_label ||
    metadata.ticket_timestamp_label ||
    metadata.asset_timestamp_label;
  const usedFallback = Boolean(
    metadata.used_ingest_time_fallback ||
      metadata.ticket_timestamp_basis === "ingested_now_missing_source_time" ||
      metadata.asset_timestamp_basis === "ingested_now_missing_source_time"
  );

  if (!label && !usedFallback) return "";
  if (label && usedFallback) return `${label} | not source-observed`;
  if (label) return label;
  return "Logged at ingest | not source-observed";
}

function buildQueueWhyNow(caseData) {
  const metadata = caseData.metadata || {};
  const notes = [];

  if (caseData.status === "ACTIVE") {
    notes.push("Active field case");
  } else if (caseData.status === "INACTIVE") {
    notes.push("Inactive watchpoint");
  } else {
    notes.push("Historical contradiction");
  }

  if (caseData.response_posture === "HOLD_WORK") {
    notes.push("Stop threshold");
  } else if (caseData.response_posture === "ESCALATE") {
    notes.push("Escalation threshold");
  } else if (caseData.response_posture === "VERIFY_BEFORE_PROCEEDING") {
    notes.push("Verification gate");
  }

  const gapSummary = formatGapSummary(
    metadata.last_status_transition?.gap_min ?? metadata.continuity_gap_min
  );
  if (gapSummary && caseData.status !== "ACTIVE") {
    notes.push(gapSummary);
  }

  const signals = buildQueueSignals(caseData);
  return [...new Set([...notes, ...signals])].slice(0, 3);
}

function inferReturnPriority(caseData) {
  const whyNow = caseData.why_now || [];
  const noTicket = whyNow.some((item) =>
    /no plausible matching ticket|without a plausible matching ticket/i.test(item || "")
  );
  const unclearCoverage = whyNow.some((item) =>
    /conflicts across overlapping ticket areas|overlapping ticket|outside.*window|time coverage conflicts|outside.*area|scope conflict/i.test(
      item || ""
    )
  );
  const heavy = hasConcern(caseData, /mechanized|heavy equipment/i);
  const trenchless = hasConcern(caseData, /reduced-visibility|trenchless|hdd|boring/i);
  const nearAsset = getEvidenceLayers(caseData).observed.some((item) =>
    /near one or more mapped assets/i.test(item?.statement || "")
  );

  if (noTicket && (heavy || trenchless || nearAsset)) {
    return {
      label: "If it returns: stop work",
      short: "Stop work if it resumes",
      rank: 3,
      detail: "no active ticket covers the work and consequence is high",
    };
  }

  if (noTicket || unclearCoverage || heavy || trenchless) {
    return {
      label: "If it returns: verify first",
      short: "Verify first if it resumes",
      rank: 2,
      detail: "ticket support is weak enough that resumed activity should be checked immediately",
    };
  }

    return {
      label: "If it returns: monitor closely",
      short: "Monitor closely if it resumes",
      rank: 1,
      detail: "nothing live needs action now, but fresh activity could change the picture quickly",
  };
}

function buildFocusAssessment(caseData) {
  const status = caseData.status || "ACTIVE";
  const reasons = [];
  let score = 0;
  const urgency = String(caseData.urgency || "LOW").toUpperCase();

  if (status === "ACTIVE") {
    score += 100;
    reasons.push("Active field case");
  } else if (status === "INACTIVE") {
    score += 55;
    reasons.push("Returns could matter");
  } else {
    score += 15;
    reasons.push("Reference only");
  }

  if (caseData.response_posture === "ESCALATE") {
    score += 35;
    reasons.push("Escalation posture");
  } else if (caseData.response_posture === "HOLD_WORK") {
    score += 45;
    reasons.push("Stop work posture");
  } else if (caseData.response_posture === "VERIFY_BEFORE_PROCEEDING") {
    score += 25;
    reasons.push("Verify before proceeding");
  } else if (caseData.response_posture === "VERIFY") {
    score += 12;
    reasons.push("Needs targeted verification");
  }

  if (urgency === "CRITICAL") {
    score += 30;
    reasons.push("Critical urgency");
  } else if (urgency === "HIGH") {
    score += 20;
    reasons.push("High urgency");
  } else if (urgency === "MODERATE") {
    score += 10;
  }

  score += Math.round(Number(caseData.uncertainty_burden || 0) * 25);
  score += Math.round((1 - Number(caseData.evaluation_confidence || 0)) * 15);
  score += Math.min((caseData.failure_layers || []).length * 4, 16);

  if ((caseData.why_now || []).some((item) => /intended area|spatial scope/i.test(item))) {
    reasons.push("Spatial contradiction");
  }
  if ((caseData.why_now || []).some((item) => /intended window|time scope/i.test(item))) {
    reasons.push("Time contradiction");
  }
  if (
    (caseData.why_now || []).some((item) => /weak|ambiguous|passive trust/i.test(item)) ||
    (caseData.information_integrity_assessment?.concerns || []).length > 0
  ) {
    reasons.push("Weak context integrity");
  }

  const uniqueReasons = [...new Set(reasons)];
  const focusLabel =
    status === "ACTIVE"
      ? caseData.response_posture === "HOLD_WORK" || caseData.response_posture === "ESCALATE"
        ? "Focus now"
        : caseData.response_posture === "VERIFY_BEFORE_PROCEEDING" || caseData.response_posture === "VERIFY"
        ? "Active"
        : "Background"
      : status === "INACTIVE"
      ? "If it returns"
      : "Reference only";

  return {
    score,
    label: focusLabel,
    reasons: uniqueReasons.slice(0, 3),
  };
}

function getStatusRank(status) {
  if (status === "ACTIVE") return 3;
  if (status === "INACTIVE") return 2;
  return 1;
}

function getPostureRank(posture) {
  if (posture === "HOLD_WORK") return 5;
  if (posture === "ESCALATE") return 4;
  if (posture === "VERIFY_BEFORE_PROCEEDING") return 3;
  if (posture === "VERIFY") return 2;
  return 1;
}

function getUrgencyRank(urgency) {
  if (urgency === "CRITICAL") return 4;
  if (urgency === "HIGH") return 3;
  if (urgency === "MODERATE") return 2;
  return 1;
}

function compareCasePriority(left, right) {
  const statusDelta = getStatusRank(right.status) - getStatusRank(left.status);
  if (statusDelta !== 0) return statusDelta;

  if (left.status === "INACTIVE" && right.status === "INACTIVE") {
    const returnDelta =
      Number(right.returnPriority?.rank || 0) - Number(left.returnPriority?.rank || 0);
    if (returnDelta !== 0) return returnDelta;
  }

  const postureDelta =
    getPostureRank(right.response_posture) - getPostureRank(left.response_posture);
  if (postureDelta !== 0) return postureDelta;

  const urgencyDelta =
    getUrgencyRank(String(right.urgency || "LOW").toUpperCase()) -
    getUrgencyRank(String(left.urgency || "LOW").toUpperCase());
  if (urgencyDelta !== 0) return urgencyDelta;

  const focusDelta = Number(right.focus?.score || 0) - Number(left.focus?.score || 0);
  if (focusDelta !== 0) return focusDelta;

  const rightTime = new Date(right.lastFieldActivityAt || 0).getTime() || 0;
  const leftTime = new Date(left.lastFieldActivityAt || 0).getTime() || 0;
  return rightTime - leftTime;
}

function buildNowState(caseData) {
  const chain = buildResponsibilityChainStory(caseData);
  const primaryRisk = buildPrimaryRisk(caseData);
  const worthStopping = buildInterruptionWorth(caseData);
  const pattern = buildPatternFrame(caseData);
  const consequence = buildConsequenceFrame(caseData);

  if (caseData.status === "CLOSED") {
    return {
      command: "NOT LIVE",
      action: "Keep as history only",
      risk: "Closed",
      primaryRisk: "No live work is active in this case",
      decisionPunchline: "No live activity remains in this case.",
      damageLine: "Watch for: only future matching activity would make this relevant again.",
      pattern,
      consequence,
      worthStopping,
    };
  }

  if (caseData.status === "INACTIVE") {
    return {
      command: "WATCH",
      action: "Wait for new activity, then verify",
      risk: "Inactive",
      primaryRisk: "No current field activity is interrupting the decision path",
      decisionPunchline: "This is not live right now, but it could matter again if activity returns.",
      damageLine: "Watch for: resumed activity could reconnect this thread before anyone notices.",
      pattern,
      consequence,
      worthStopping,
    };
  }

  if (caseData.response_posture === "HOLD_WORK") {
    return {
      command: "STOP WORK",
      action: caseData.recommended_actions?.[0] || "Pause and verify ticket plus location",
      risk: "Critical",
      primaryRisk,
      decisionPunchline: buildDecisionPunchline(caseData),
      damageLine: buildDamageLine(caseData),
      pattern,
      consequence,
      worthStopping,
    };
  }

  if (caseData.response_posture === "ESCALATE") {
    return {
      command: "ESCALATE",
      action: caseData.recommended_actions?.[0] || "Escalate for active review",
      risk: "High",
      primaryRisk,
      decisionPunchline: buildDecisionPunchline(caseData),
      damageLine: buildDamageLine(caseData),
      pattern,
      consequence,
      worthStopping,
    };
  }

  if (caseData.response_posture === "VERIFY_BEFORE_PROCEEDING") {
    return {
      command: "VERIFY BEFORE PROCEEDING",
      action: caseData.recommended_actions?.[0] || "Pause and verify ticket plus location",
      risk: "Elevated",
      primaryRisk,
      decisionPunchline: buildDecisionPunchline(caseData),
      damageLine: buildDamageLine(caseData),
      pattern,
      consequence,
      worthStopping,
    };
  }

  return {
    command: chain.command.toUpperCase(),
    action: caseData.recommended_actions?.[0] || "Monitor while keeping it visible",
    risk: titleCaseFromEnum(caseData.urgency),
    primaryRisk: chain.reason || primaryRisk,
    decisionPunchline: buildDecisionPunchline(caseData),
    damageLine: "Watch for: support could weaken fast if scope, timing, or activity changes.",
    pattern,
    consequence,
    worthStopping,
  };
}

function buildActionTabMeta(caseData) {
  if (caseData.status === "CLOSED") {
    return {
      eyebrow: "Historical Context",
      title: "Why this case stays closed",
      patternTitle: "What happened here",
      weakTitle: "Why it closed",
      actionTitle: "What would matter next time",
      consequenceTitle: "Why keep it on record",
      thresholdTitle: "Reopen threshold",
      whyNowTitle: "Why it changed",
    };
  }

  if (caseData.status === "INACTIVE") {
    return {
      eyebrow: "Watch For Return",
      title: "Why this case is inactive",
      patternTitle: "What looked normal",
      weakTitle: "What changed",
      actionTitle: "What to check if it returns",
      consequenceTitle: "Why it still matters",
      thresholdTitle: "Reactivation threshold",
      whyNowTitle: "Why it changed",
    };
  }

  if (caseData.response_posture === "MONITOR") {
    return {
      eyebrow: "Keep In View",
      title: hasDegradedResponsibilitySupport(caseData)
        ? "Why this stays visible"
        : "Why this is not being interrupted",
      patternTitle: "What is supporting the decision",
      weakTitle: "Chain weakness",
      actionTitle: "What to watch",
      consequenceTitle: "Why keep it visible",
      thresholdTitle: "Why we are not stepping in",
      whyNowTitle: "What the system is watching",
    };
  }

  return {
    eyebrow: "Do Not Trust This Yet",
    title: "Why you should not trust this situation",
    patternTitle: "What looks normal",
    weakTitle: "What is weak",
    actionTitle: "Next steps",
    consequenceTitle: "Why it is not normal enough",
    thresholdTitle: "Why we are stepping in",
    whyNowTitle: "Why now",
  };
}

function buildOutcomeLabel(caseData) {
  if (caseData.status === "CLOSED" || caseData.status === "INACTIVE") {
    return "Watch for";
  }

  if (caseData.response_posture === "MONITOR") {
    return "Watch for";
  }

  return "Consequence";
}

function buildChangeSummary(caseData) {
  const trend = String(caseData.temporal_change?.trend || caseData.trend || "").toUpperCase();
  const change = caseData.temporal_change?.change_summary || {};
  const hasDimensionalShift = Object.values(change).some(
    (value) => !["unchanged", "none", "stable", "same"].includes(String(value || "").toLowerCase())
  );

  if (trend === "WORSENING") {
    return {
      label: "Moved Up",
      detail: "This case got more serious relative to its prior saved state.",
      tone: "warning",
    };
  }

  if (trend === "IMPROVING") {
    return {
      label: "Moved Down",
      detail: "This case eased relative to its prior saved state.",
      tone: "low",
    };
  }

  if (trend === "REACTIVATED") {
    return {
      label: "Reactivated",
      detail: "This case came back after previously dropping out of live continuity.",
      tone: "warning",
    };
  }

  if (trend === "NEW") {
    return {
      label: "New Case",
      detail: "There is no older saved state to compare against yet.",
      tone: "neutral",
    };
  }

  if (hasDimensionalShift) {
    return {
      label: "Shifted",
      detail: "Some dimensions changed, but not enough to change the overall trend.",
      tone: "neutral",
    };
  }

  return {
    label: "Stable",
    detail: "No meaningful dimensional shift was recorded relative to the prior saved state.",
    tone: "neutral",
  };
}

function buildTrendMeta(caseData) {
  const trend = String(
    caseData.temporal_change?.trend || caseData.trend || caseData.metadata?.trend || "STABLE"
  ).toUpperCase();

  if (trend === "WORSENING") {
    return { value: "WORSENING", label: "Getting worse", tone: "warning" };
  }
  if (trend === "IMPROVING") {
    return { value: "IMPROVING", label: "Getting better", tone: "low" };
  }
  if (trend === "REACTIVATED") {
    return { value: "REACTIVATED", label: "Active again", tone: "warning" };
  }
  if (trend === "NEW") {
    return { value: "NEW", label: "New", tone: "neutral" };
  }
  return { value: "STABLE", label: "Neutral", tone: "neutral" };
}

function buildEvolutionSummary(caseData) {
  const eventSeries = (caseData.observations || [])
    .filter((item) => item?.observation_type === "EVENT_SEEN")
    .map((item) => ({
      when: normalizeTimelineTime(item?.metadata?.event_time || caseData.updated_at),
      eventType: String(item?.value || "").trim(),
      equipment: String(item?.metadata?.equipment_type || "").trim(),
    }))
    .filter((item) => item.when)
    .sort((left, right) => left.when.getTime() - right.when.getTime());

  if (eventSeries.length === 0) {
    return [];
  }

  const items = [];
  const first = eventSeries[0];
  const last = eventSeries[eventSeries.length - 1];

  if (eventSeries.length > 1) {
    items.push(
      `Seen across ${eventSeries.length} field updates from ${formatDateTime(first.when)} to ${formatDateTime(last.when)}.`
    );
  } else {
    items.push(`Only one field update has been attached so far, at ${formatDateTime(first.when)}.`);
  }

  const eventTypes = [...new Set(eventSeries.map((item) => item.eventType).filter(Boolean))];
  if (eventTypes.length > 1) {
    items.push(
      `Activity shifted from ${eventTypes[0]} to ${eventTypes[eventTypes.length - 1]}.`
    );
  }

  const equipmentRank = {
    locator: 0,
    "hand crew": 1,
    "hand dig": 1,
    inspection: 1,
    "vacuum truck": 2,
    "mini excavator": 3,
    backhoe: 4,
    "directional drill": 5,
    "hdd rig": 5,
  };
  const equipmentSeries = eventSeries.map((item) => item.equipment).filter(Boolean);
  if (equipmentSeries.length > 1) {
    const firstEquipment = equipmentSeries[0];
    const lastEquipment = equipmentSeries[equipmentSeries.length - 1];
    const firstRank = equipmentRank[firstEquipment] ?? 1;
    const lastRank = equipmentRank[lastEquipment] ?? 1;
    if (lastRank > firstRank) {
      items.push(`Equipment escalated from ${firstEquipment} to ${lastEquipment}.`);
    }
  }

  const gapMinutes = Number(
    caseData.metadata?.last_status_transition?.gap_min ?? caseData.metadata?.continuity_gap_min
  );
  if (caseData.status === "INACTIVE" && Number.isFinite(gapMinutes)) {
    items.push(
      `Then activity went quiet long enough to move this case out of the live queue.`
    );
  }
  if (caseData.status === "CLOSED" && Number.isFinite(gapMinutes)) {
    items.push(`Then the thread stayed quiet long enough to drop into reference-only history.`);
  }
  if (caseData.status === "ACTIVE" && eventSeries.length > 1) {
    items.push(`Fresh activity is still extending the same thread right now.`);
  }

  return [...new Set(items)].slice(0, 4);
}

function mapBackendCaseToView(caseData) {
  const contradiction = buildContradiction(caseData);
  const status = caseData.status || "ACTIVE";
  const actionableNow = status === "ACTIVE";
  const focus = buildFocusAssessment(caseData);
  const authorizationClarity = buildAuthorizationClarity(caseData);
  const lifecycle = buildLifecycleContext(caseData);
  const returnPriority = inferReturnPriority(caseData);
  const decisionConfidence = buildDecisionConfidence(caseData);
  const evidenceSnapshot = buildEvidenceSnapshot(caseData);
  const hiddenRisk = buildHiddenRiskAssessment(caseData);
  const informationGap = buildInformationGapAssessment(caseData);
  const conflictLayer = buildConflictAssessment(caseData);
  const chainStory = buildResponsibilityChainStory(caseData);

  return {
    ...caseData,
    status,
    actionableNow,
    tone: getCaseTone({ ...caseData, status }),
    contradiction,
    contradictionMeta: buildContradictionMeta(caseData),
    preconditions: buildOperatorBelief(caseData),
    breaks: buildRealityBreaks(caseData),
    actions: buildActionList(caseData),
    evidenceFeed: buildEvidenceFeed(caseData),
    timeline: buildTimeline(caseData),
    focus,
    authorizationClarity,
    weakSupport: buildWeakSupportList(caseData),
    supportStatus: buildSupportStatus(caseData),
    returnPriority,
    decisionConfidence,
    evidenceSnapshot,
    escalationSummary: buildEscalationSummary(caseData),
    hiddenRisk,
    informationGap,
    conflictLayer,
    outcomeLabel: buildOutcomeLabel(caseData),
    lifecycle,
    nowState: buildNowState(caseData),
    changeSummary: buildChangeSummary(caseData),
    trendMeta: buildTrendMeta(caseData),
    evolutionSummary: buildEvolutionSummary(caseData),
    actionTabMeta: buildActionTabMeta(caseData),
    chainStory,
    queueReason: summarizeQueueReason(caseData),
    queueWhyNow: buildQueueWhyNow(caseData),
    lastFieldActivityAt: getLatestFieldEventTime(caseData),
    headline:
      status === "CLOSED"
        ? "Closed case, not a live interruption"
        : status === "INACTIVE"
        ? "Inactive case, watch for reactivation"
        : caseData.response_posture === "HOLD_WORK"
        ? "Stop required"
        : caseData.response_posture === "ESCALATE"
        ? "Interrupt and escalate"
        : caseData.response_posture === "VERIFY_BEFORE_PROCEEDING"
        ? "Verify before continuing"
        : chainStory.command,
  };
}

function StatCard({ label, value, detail }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
      {detail ? <span className="stat-detail">{detail}</span> : null}
    </div>
  );
}

function TonePill({ tone, children }) {
  return <span className={`tone-pill tone-pill--${tone}`}>{children}</span>;
}

function getLifecycleBadge(caseData) {
  if (caseData.status === "CLOSED") {
    return { tone: "closed", label: "CLOSED" };
  }

  if (caseData.status === "INACTIVE") {
    return { tone: "inactive", label: "INACTIVE" };
  }

  return {
    tone: scoreTone(caseData.urgency),
    label: caseData.urgency || "LOW",
  };
}

function QueueCard({ item, selected, onSelect }) {
  const locationLine = buildQueueLocation(item);
  const evidenceLine =
    buildQueueEvidenceLine(item) ||
    item.weakSupport?.[0] ||
    `Last activity ${formatDateTime(item.lastFieldActivityAt)}`;
  const actionLabel =
    item.response_posture === "HOLD_WORK"
      ? "STOP"
      : item.response_posture === "ESCALATE"
      ? "ESCALATE"
      : item.response_posture === "VERIFY_BEFORE_PROCEEDING"
      ? "VERIFY"
      : "MONITOR";

  return (
    <button
      type="button"
      className={`queue-card ${selected ? "queue-card--selected" : ""}`}
      onClick={onSelect}
    >
      <div className="queue-card__topline">
        <strong className="queue-card__case">Case {item.case_id}</strong>
        <TonePill tone={item.tone}>{actionLabel}</TonePill>
      </div>
      <p className="queue-card__summary">{item.queueReason}</p>
      <p className="queue-card__focus">{evidenceLine}</p>
      <div className="queue-card__meta">
        <span>{locationLine}</span>
        <span>{formatDateTime(item.lastFieldActivityAt)}</span>
      </div>
    </button>
  );
}

function LayerCard({ item, assessment, listTitle, onSelect }) {
  return (
    <button type="button" className="hidden-risk-card" onClick={onSelect}>
      <div className="hidden-risk-card__topline">
        <span className="queue-card__id">Case {item.case_id}</span>
        <TonePill tone={item.tone}>
          {item.status === "ACTIVE" ? item.urgency || "LOW" : item.status}
        </TonePill>
        <TonePill tone="neutral">{titleCaseFromEnum(item.response_posture)}</TonePill>
      </div>
      <strong className="hidden-risk-card__title">{assessment.title}</strong>
      <p className="hidden-risk-card__summary">{assessment.detail}</p>
      <div className="snapshot-grid snapshot-grid--compact">
        {item.evidenceSnapshot.slice(0, 4).map((snapshot) => (
          <div className="snapshot-card" key={`${item.case_id}-${snapshot.label}`}>
            <span className="snapshot-card__label">{snapshot.label}</span>
            <strong className="snapshot-card__value">{snapshot.value}</strong>
            <span className="snapshot-card__detail">{snapshot.detail}</span>
          </div>
        ))}
      </div>
      <div className="hidden-risk-card__list">
        <ListBlock
          title={listTitle}
          items={assessment.reasons}
          emptyLabel="No layer-specific reasons were returned."
        />
      </div>
      <div className="queue-card__meta">
        <span>{item.headline}</span>
        <span>Last field activity {formatDateTime(item.lastFieldActivityAt)}</span>
      </div>
    </button>
  );
}

function QueueSection({ title, detail, items, selectedId, onSelect }) {
  const allClosed = items.every((item) => item.status === "CLOSED");
  const defaultExpanded = allClosed ? false : items.length <= 6;
  const [expanded, setExpanded] = useState(defaultExpanded);
  const visibleItems = expanded ? items : items.slice(0, allClosed ? 0 : 6);
  if (items.length === 0) return null;

  return (
    <div className="queue-section">
      <div className="queue-section__header">
        <div className="queue-section__heading">
          <strong>{title}</strong>
          <span>{detail}</span>
        </div>
        {items.length > 6 || allClosed ? (
          <button
            type="button"
            className="queue-section__toggle"
            onClick={() => setExpanded((current) => !current)}
          >
            {expanded
              ? allClosed
                ? `Hide ${items.length} cases`
                : `Show fewer`
              : `Show ${items.length} cases`}
          </button>
        ) : null}
      </div>
      <div className="queue-section__list">
        {visibleItems.map((item) => (
          <QueueCard
            key={item.case_id}
            item={item}
            selected={item.case_id === selectedId}
            onSelect={() => onSelect(item.case_id)}
          />
        ))}
      </div>
    </div>
  );
}

function StableCasesSummary({ count, onOpen }) {
  if (count <= 0) return null;

  return (
    <section className="stable-summary">
      <div className="stable-summary__copy">
        <span className="queue__eyebrow">Stable</span>
        <strong>{count} stable active case{count === 1 ? "" : "s"} with no new degradation</strong>
        <p>
          Monitored for now, but still exposed if conditions change. Keep them visible without
          letting them compete with the cases that need a decision change right now.
        </p>
      </div>
      <button type="button" className="stable-summary__button" onClick={onOpen}>
        Open stable cases
      </button>
    </section>
  );
}

function QuickPresetButton({ active, label, detail, onClick, secondary = false }) {
  return (
    <button
      type="button"
      className={`preset-chip ${active ? "preset-chip--active" : ""} ${secondary ? "preset-chip--secondary" : ""}`}
      onClick={onClick}
    >
      <strong>{label}</strong>
      <span>{detail}</span>
    </button>
  );
}

function WorkspacePageButton({ active, label, detail, onClick }) {
  return (
    <button
      type="button"
      className={`workspace-nav__button ${active ? "workspace-nav__button--active" : ""}`}
      onClick={onClick}
    >
      <strong>{label}</strong>
      <span>{detail}</span>
    </button>
  );
}

function OverviewSignalCard({ eyebrow, title, detail, count, caseItem, onOpenQueue, onOpenCase }) {
  return (
    <section className="signal-card">
      <span className="queue__eyebrow">{eyebrow}</span>
      <h3>{title}</h3>
      <p>{detail}</p>
      <div className="signal-card__meta">
        <strong>{count}</strong>
        <span>{count === 1 ? "case in this slice" : "cases in this slice"}</span>
      </div>
      {caseItem ? (
        <div className="signal-card__case">
          <div className="signal-card__case-topline">
            <span>Case {caseItem.case_id}</span>
            <TonePill tone={caseItem.tone}>
              {caseItem.status === "ACTIVE" ? caseItem.urgency || "LOW" : caseItem.status}
            </TonePill>
          </div>
          <strong>{caseItem.nowState.command}</strong>
          <p>{caseItem.queueReason}</p>
        </div>
      ) : (
        <div className="signal-card__case signal-card__case--empty">
          <p>No cases are surfacing here right now.</p>
        </div>
      )}
      <div className="signal-card__actions">
        <button type="button" className="stable-summary__button" onClick={onOpenQueue}>
          Open in queue
        </button>
        {caseItem ? (
          <button
            type="button"
            className="landing-spotlight__button signal-card__button"
            onClick={() => onOpenCase(caseItem.case_id)}
          >
            Open case
          </button>
        ) : null}
      </div>
    </section>
  );
}

function LandingChangeCard({ caseItem, direction }) {
  const riskier = direction === "riskier";
  const label = riskier ? "Riskier" : "Safer";
  const detail =
    caseItem?.changeSummary?.detail ||
    caseItem?.temporal_change?.true_what_changed?.[0] ||
    caseItem?.queueReason ||
    "No change detail was returned.";

  return (
    <article className={`landing-change-card landing-change-card--${direction}`}>
      <div className="landing-change-card__topline">
        <span>{label}</span>
        <strong>Case {caseItem.case_id}</strong>
      </div>
      <p>{detail}</p>
      <div className="landing-change-card__meta">
        <span>{titleCaseFromEnum(caseItem.response_posture)}</span>
        <span>{caseItem.chainStory?.supportState ? titleCaseFromEnum(caseItem.chainStory.supportState) : caseItem.changeSummary.label}</span>
      </div>
    </article>
  );
}

function LandingPage({
  spotlightCase,
  riskierCases,
  saferCases,
  stopCount,
  escalateCount,
  verifyCount,
  monitorActiveCount,
  onOpenQueue,
}) {
  return (
    <section className="landing-page">
      <div className="landing-page__intro">
        <span className="hero__kicker">Riskseer</span>
        <h1>Start with the call that can't wait.</h1>
        <p>
          One immediate case, then the queue. Trend changes are shown for context only.
        </p>
      </div>

      <section className="landing-attention">
        <div className="landing-attention__copy">
          <span className="queue__eyebrow">Most Immediate Attention</span>
          {spotlightCase ? (
            <>
              <div className="landing-spotlight__topline">
                <TonePill tone={spotlightCase.tone}>
                  {spotlightCase.status === "ACTIVE"
                    ? spotlightCase.urgency || "LOW"
                    : spotlightCase.status}
                </TonePill>
                <TonePill tone="neutral">{spotlightCase.nowState.command}</TonePill>
              </div>
              <h2>Case {spotlightCase.case_id}</h2>
              <p>{spotlightCase.nowState.decisionPunchline}</p>
              <div className="landing-attention__reason">
                <strong>
                  {spotlightCase.chainStory?.supportState
                    ? titleCaseFromEnum(spotlightCase.chainStory.supportState)
                    : "Decision support"}
                </strong>
                <span>{spotlightCase.chainStory?.reason || spotlightCase.queueReason}</span>
              </div>
            </>
          ) : (
            <>
              <h2>No immediate case</h2>
              <p>No live work is currently being prioritized.</p>
            </>
          )}
        </div>
        <div className="landing-attention__side">
          <div className="landing-counts">
            <StatCard label="Stop" value={stopCount} detail="Pause work" />
            <StatCard label="Escalate" value={escalateCount} detail="Human review" />
            <StatCard label="Verify" value={verifyCount} detail="Check support" />
            <StatCard label="Monitor" value={monitorActiveCount} detail="Keep visible" />
          </div>
          <button type="button" className="landing-primary-action" onClick={onOpenQueue}>
            Open queue
          </button>
        </div>
      </section>

      <section className="landing-changes" aria-label="What changed">
        <div className="landing-changes__header">
          <span className="queue__eyebrow">What Changed</span>
          <p>Display only. Open the queue to select and drill into cases.</p>
        </div>
        <div className="landing-changes__grid">
          <div className="landing-change-column">
            <h2>Became riskier</h2>
            {riskierCases.length === 0 ? (
              <p className="landing-change-empty">No worsening cases returned.</p>
            ) : (
              riskierCases.slice(0, 2).map((item) => (
                <LandingChangeCard key={`riskier-${item.case_id}`} caseItem={item} direction="riskier" />
              ))
            )}
          </div>
          <div className="landing-change-column">
            <h2>Trending safer</h2>
            {saferCases.length === 0 ? (
              <p className="landing-change-empty">No improving cases returned.</p>
            ) : (
              saferCases.slice(0, 2).map((item) => (
                <LandingChangeCard key={`safer-${item.case_id}`} caseItem={item} direction="safer" />
              ))
            )}
          </div>
        </div>
      </section>
    </section>
  );
}
function Panel({ eyebrow, title, children, tone = "default" }) {
  return (
    <section className={`panel panel--${tone}`}>
      <div className="panel__eyebrow">{eyebrow}</div>
      <h2 className="panel__title">{title}</h2>
      {children}
    </section>
  );
}

function ListBlock({ title, items, emptyLabel }) {
  return (
    <div className="list-block">
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p className="list-block__empty">{emptyLabel}</p>
      ) : (
        <ul>
          {items.map((item, index) => (
            <li key={`${title}-${index}`}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ResponsibilityIntegrityPanel({ caseData }) {
  const chain = buildResponsibilityChainStory(caseData);
  const decisionSupport = getDecisionSupport(caseData);

  if (chain.layerItems.length === 0) return null;

  return (
    <Panel
      eyebrow="Responsibility Chain"
      title={`${chain.command} - ${titleCaseFromEnum(chain.supportState || "Decision support")}`}
      tone="default"
    >
      <p className="panel-summary">
        {chain.reason}
      </p>
      <div className="snapshot-grid snapshot-grid--compact">
        {chain.layerItems.map((layer) => (
          <div className="snapshot-card" key={layer.key}>
            <span className="snapshot-card__label">{layer.label}</span>
            <strong className="snapshot-card__value">{titleCaseFromEnum(layer.state)}</strong>
            <span className="snapshot-card__detail">{layer.reason}</span>
          </div>
        ))}
      </div>
      <div className="action-grid">
        <ListBlock
          title="Decision support"
          items={[
            `Risk: ${titleCaseFromEnum(chain.decisionRisk || "UNKNOWN")}`,
            `Posture: ${titleCaseFromEnum(decisionSupport.recommended_posture || caseData.response_posture)}`,
          ]}
          emptyLabel="No decision support summary was returned."
        />
        <ListBlock
          title="Propagation"
          items={chain.propagation.slice(0, 4)}
          emptyLabel="No propagation path was returned."
        />
      </div>
    </Panel>
  );
}

function DecisionDefensibilityPanel({ caseData }) {
  const defensibility = getDecisionDefensibility(caseData);
  const state = String(defensibility.state || "").toUpperCase();
  if (!state) return null;

  const components = defensibility.components && typeof defensibility.components === "object"
    ? defensibility.components
    : {};
  const weaknesses = Array.isArray(defensibility.key_weaknesses)
    ? defensibility.key_weaknesses
    : [];

  return (
    <Panel
      eyebrow="Defensibility"
      title={`${titleCaseFromEnum(state)} if reviewed now`}
      tone={state === "LOW" ? "danger" : state === "MODERATE" ? "warning" : "default"}
    >
      <p className="panel-summary">
        {defensibility.reason || "No defensibility reason was returned by the backend."}
      </p>
      <div className="action-grid">
        <ListBlock
          title="Why it may not hold"
          items={weaknesses.slice(0, 4)}
          emptyLabel="No material defensibility weaknesses were returned."
        />
        <ListBlock
          title="Review basis"
          items={[
            `Decision risk: ${titleCaseFromEnum(defensibility.decision_risk || "UNKNOWN")}`,
            defensibility.defensible_decision
              ? `Defensible decision: ${titleCaseFromEnum(defensibility.defensible_decision)}`
              : null,
            components.evidence_sufficiency,
            components.verification_depth,
            components.assumption_load,
          ].filter(Boolean).slice(0, 4)}
          emptyLabel="No defensibility components were returned."
        />
      </div>
    </Panel>
  );
}

function RelatedCasesBlock({ items, onSelect }) {
  return (
    <div className="list-block">
      <h3>Potentially related cases</h3>
      {items.length === 0 ? (
        <p className="list-block__empty">No linked cases were returned for this case.</p>
      ) : (
        <div className="related-case-list">
          {items.map((item) => {
            const badge = getLifecycleBadge(item);
            return (
            <button
              key={item.case_id}
              type="button"
              className="related-case-card"
              onClick={() => onSelect(item.case_id)}
            >
              <div className="related-case-card__topline">
                <strong>Case {item.case_id}</strong>
                <TonePill tone={badge.tone}>{badge.label}</TonePill>
              </div>
              <div className="queue-card__meta">
                <span>{titleCaseFromEnum(item.status)}</span>
                <span>{titleCaseFromEnum(item.response_posture)}</span>
              </div>
              <p className="queue-card__summary">{item.headline}</p>
              <p className="related-case-card__reason">
                Link reason: {titleCaseFromEnum(item.branch_reason || "related_case")}
              </p>
            </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function EvidenceRow({ item }) {
  return (
    <div className="evidence-row">
      <div className="evidence-row__lane">{item.lane}</div>
      <div className="evidence-row__body">
        <p>{item.statement || item.summary}</p>
        <div className="evidence-row__meta">
          {Array.isArray(item.source_ids) && item.source_ids.length > 0 ? (
            <span>Sources: {item.source_ids.join(", ")}</span>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function TimelineItem({ item, index }) {
  const timestampDescriptor = describeTimelineTimestamp(item);

  return (
    <div className="timeline-item">
      <div className="timeline-item__rail">
        <span className="timeline-item__dot" />
        {index > -1 ? <span className="timeline-item__line" /> : null}
      </div>
      <div className="timeline-item__content">
        <div className="timeline-item__topline">
          <strong>{item.label}</strong>
          <span>{formatDateTime(item.when)}</span>
        </div>
        {timestampDescriptor ? (
          <div className="timeline-item__stamp">{timestampDescriptor}</div>
        ) : null}
        <p>{item.summary}</p>
        <details className="timeline-item__details">
          <summary>Rough overview</summary>
          <div>{item.detail}</div>
        </details>
      </div>
    </div>
  );
}

export default function App() {
  const [cases, setCases] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [activeTab, setActiveTab] = useState("decision");
  const [activePage, setActivePage] = useState("landing");
  const [filters, setFilters] = useState({
    search: "",
    status: "ALL",
    posture: "ALL",
    urgency: "ALL",
    trend: "ALL",
    failureLayer: "ALL",
    relatedOnly: false,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [investigations, setInvestigations] = useState({});
  const [investigationLoading, setInvestigationLoading] = useState(false);
  const [investigationError, setInvestigationError] = useState("");

  useEffect(() => {
    async function fetchCases() {
      try {
        setError("");
        const casesUrl = STATIC_DEMO
          ? `${import.meta.env.BASE_URL}demo_cases.json`
          : `${API_BASE}/api/cases`;
        const response = await fetch(casesUrl);

        if (!response.ok) {
          throw new Error(`Backend returned ${response.status}`);
        }

        const data = await response.json();
        const nextCases = Array.isArray(data.cases)
          ? data.cases.map(mapBackendCaseToView)
          : [];

        setCases(nextCases);
        if (nextCases.length > 0) {
          setSelectedId((current) => current ?? nextCases[0].case_id);
        }
      } catch (fetchError) {
        console.error(fetchError);
        setError(String(fetchError.message || fetchError));
      } finally {
        setLoading(false);
      }
    }

    fetchCases();
  }, []);

  const casesWithRelations = useMemo(() => {
    const byId = new Map(cases.map((item) => [item.case_id, item]));

    return cases.map((item) => ({
      ...item,
      relatedCases: [...new Set(getCaseRelationIds(item))]
        .map((id) => byId.get(id))
        .filter(Boolean)
        .map((related) => ({
          case_id: related.case_id,
          urgency: related.urgency,
          status: related.status,
          response_posture: related.response_posture,
          headline: related.headline,
          operator_summary: related.operator_summary,
          branch_reason:
            related.branch_reason ||
            (related.parent_case_id === item.case_id || item.parent_case_id === related.case_id
              ? "parent_child_relationship"
              : "related_case"),
        })),
    }));
  }, [cases]);

  const availableFailureLayers = useMemo(
    () =>
      [...new Set(casesWithRelations.map((item) => item.primary_failure_layer).filter(Boolean))].sort(),
    [casesWithRelations]
  );

  const statusCounts = useMemo(() => {
    const counts = {};
    for (const item of casesWithRelations) {
      counts[item.status] = (counts[item.status] || 0) + 1;
    }
    return counts;
  }, [casesWithRelations]);

  const postureCounts = useMemo(() => {
    const counts = {};
    for (const item of casesWithRelations) {
      counts[item.response_posture] = (counts[item.response_posture] || 0) + 1;
    }
    return counts;
  }, [casesWithRelations]);

  const urgencyCounts = useMemo(() => {
    const counts = {};
    for (const item of casesWithRelations) {
      counts[item.urgency] = (counts[item.urgency] || 0) + 1;
    }
    return counts;
  }, [casesWithRelations]);

  const trendCounts = useMemo(() => {
    const counts = {};
    for (const item of casesWithRelations) {
      const trend = item.trendMeta?.value || "STABLE";
      counts[trend] = (counts[trend] || 0) + 1;
    }
    return counts;
  }, [casesWithRelations]);

  const failureLayerCounts = useMemo(() => {
    const counts = {};
    for (const item of casesWithRelations) {
      const layer = item.primary_failure_layer;
      if (!layer) continue;
      counts[layer] = (counts[layer] || 0) + 1;
    }
    return counts;
  }, [casesWithRelations]);

  const filteredCases = useMemo(
    () => casesWithRelations.filter((item) => matchesFilters(item, filters)),
    [casesWithRelations, filters]
  );

  const _presetCounts = useMemo(
    () => ({
      stopRequired: casesWithRelations.filter(
        (item) => item.status === "ACTIVE" && item.response_posture === "HOLD_WORK"
      ).length,
      escalateNow: casesWithRelations.filter(
        (item) => item.status === "ACTIVE" && item.response_posture === "ESCALATE"
      ).length,
      verifyNow: casesWithRelations.filter(
        (item) =>
          item.status === "ACTIVE" &&
          item.response_posture === "VERIFY_BEFORE_PROCEEDING"
      ).length,
      keepMoving: casesWithRelations.filter(
        (item) => item.status === "ACTIVE" && item.response_posture === "MONITOR"
      ).length,
    }),
    [casesWithRelations]
  );

  const _hiddenRiskCases = useMemo(
    () =>
      [...casesWithRelations]
        .filter((item) => item.hiddenRisk?.eligible)
        .sort((left, right) => {
          const hiddenDelta =
            Number(right.hiddenRisk?.score || 0) - Number(left.hiddenRisk?.score || 0);
          if (hiddenDelta !== 0) return hiddenDelta;
          return compareCasePriority(left, right);
        }),
    [casesWithRelations]
  );
  const _stableActiveCases = useMemo(
    () =>
      [...filteredCases]
        .filter((item) => item.status === "ACTIVE" && item.response_posture === "MONITOR")
        .sort(compareCasePriority),
    [filteredCases]
  );

  const riskierCases = useMemo(
    () =>
      [...casesWithRelations]
        .filter((item) => ["WORSENING", "REACTIVATED"].includes(item.trendMeta?.value))
        .sort(compareCasePriority),
    [casesWithRelations]
  );

  const saferCases = useMemo(
    () =>
      [...casesWithRelations]
        .filter((item) => item.trendMeta?.value === "IMPROVING")
        .sort(compareCasePriority),
    [casesWithRelations]
  );

  const _informationGapCases = useMemo(
    () =>
      [...casesWithRelations]
        .filter((item) => item.informationGap?.eligible)
        .sort((left, right) => {
          const delta =
            Number(right.informationGap?.score || 0) - Number(left.informationGap?.score || 0);
          if (delta !== 0) return delta;
          return compareCasePriority(left, right);
        }),
    [casesWithRelations]
  );

  const _conflictCases = useMemo(
    () =>
      [...casesWithRelations]
        .filter((item) => item.conflictLayer?.eligible)
        .sort((left, right) => {
          const delta =
            Number(right.conflictLayer?.score || 0) - Number(left.conflictLayer?.score || 0);
          if (delta !== 0) return delta;
          return compareCasePriority(left, right);
        }),
    [casesWithRelations]
  );

  const selected = useMemo(
    () =>
      filteredCases.find((item) => item.case_id === selectedId) ??
      casesWithRelations.find((item) => item.case_id === selectedId) ??
      filteredCases[0] ??
      casesWithRelations[0] ??
      null,
    [casesWithRelations, filteredCases, selectedId]
  );

  useEffect(() => {
    setActiveTab("decision");
  }, [selectedId]);

  useEffect(() => {
    if (filteredCases.length === 0) return;
    if (!filteredCases.some((item) => item.case_id === selectedId)) {
      setSelectedId(filteredCases[0].case_id);
    }
  }, [filteredCases, selectedId]);

  const queueSections = useMemo(() => {
    const sorted = [...filteredCases].sort(compareCasePriority);

    return [
      {
        title: "Stop now",
        detail: "Work should pause before the crew keeps moving.",
        items: sorted.filter(
          (item) => item.status === "ACTIVE" && item.response_posture === "HOLD_WORK"
        ),
      },
      {
        title: "Escalate now",
        detail: "A person should step in before this gets waved through.",
        items: sorted.filter(
          (item) => item.status === "ACTIVE" && item.response_posture === "ESCALATE"
        ),
      },
      {
        title: "Verify now",
        detail: "The work might be okay, but only after checking what no longer lines up.",
        items: sorted.filter(
          (item) =>
            item.status === "ACTIVE" &&
            item.response_posture === "VERIFY_BEFORE_PROCEEDING"
        ),
      },
      {
        title: "Monitor",
        detail: "No interruption is recommended, but chain support still stays visible.",
        items: sorted.filter(
          (item) => item.status === "ACTIVE" && item.response_posture === "MONITOR"
        ),
      },
      {
        title: "Not active",
        detail: "These are not live right now, but could matter again if activity returns.",
        items: sorted.filter((item) => item.status === "INACTIVE"),
      },
      {
        title: "History",
        detail: "Reference only. Keep available, but out of the main decision path.",
        items: sorted.filter((item) => item.status === "CLOSED"),
      },
    ];
  }, [filteredCases]);

  const stopCount = filteredCases.filter(
    (item) => item.status === "ACTIVE" && item.response_posture === "HOLD_WORK"
  ).length;
  const escalateCount = filteredCases.filter(
    (item) => item.status === "ACTIVE" && item.response_posture === "ESCALATE"
  ).length;
  const verifyCount = filteredCases.filter(
    (item) =>
      item.status === "ACTIVE" &&
      item.response_posture === "VERIFY_BEFORE_PROCEEDING"
  ).length;
  const activeCount = filteredCases.filter((item) => item.status === "ACTIVE").length;
  const watchCount = filteredCases.filter((item) => item.status === "INACTIVE").length;
  const closedCount = filteredCases.filter((item) => item.status === "CLOSED").length;
  const monitorActiveCount = filteredCases.filter(
    (item) => item.status === "ACTIVE" && item.response_posture === "MONITOR"
  ).length;
  const spotlightCase =
    [...filteredCases].sort(compareCasePriority)[0] ??
    selected;
  const _hiddenRiskSpotlight = _hiddenRiskCases[0] ?? null;
  const _informationGapSpotlight = _informationGapCases[0] ?? null;
  const _conflictSpotlight = _conflictCases[0] ?? null;
  const activeFilterChips = [
    filters.search ? `Search: ${filters.search}` : null,
    filters.status !== "ALL" ? `Status: ${titleCaseFromEnum(filters.status)}` : null,
    filters.posture !== "ALL" ? `Action: ${titleCaseFromEnum(filters.posture)}` : null,
    filters.urgency !== "ALL" ? `Urgency: ${titleCaseFromEnum(filters.urgency)}` : null,
    filters.trend !== "ALL" ? `Trend: ${titleCaseFromEnum(filters.trend)}` : null,
    filters.failureLayer !== "ALL"
      ? `Reason: ${titleCaseFromEnum(filters.failureLayer)}`
      : null,
    filters.relatedOnly ? "Linked cases only" : null,
  ].filter(Boolean);

  const resetFilters = () =>
    setFilters({
      search: "",
      status: "ALL",
      posture: "ALL",
      urgency: "ALL",
      trend: "ALL",
      failureLayer: "ALL",
      relatedOnly: false,
    });

  const setFilterPreset = (preset) => {
    setFilters((current) => ({
      ...current,
      ...preset,
    }));
  };

  const navigateToPage = (page) => {
    setActivePage(page);
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const openCase = (caseId) => {
    setSelectedId(caseId);
    navigateToPage("case");
  };

  const openTopCaseInQueue = () => {
    if (spotlightCase?.case_id) {
      setSelectedId(spotlightCase.case_id);
    }
    navigateToPage("queue");
  };

  const runInvestigation = async () => {
    if (!selected?.case_id || investigationLoading) return;
    if (STATIC_DEMO) {
      setInvestigationError(
        "The public demo uses deterministic fixture data. Run the API locally to use the OpenAI Investigator."
      );
      return;
    }
    setInvestigationLoading(true);
    setInvestigationError("");
    try {
      const response = await fetch(
        `${API_BASE}/api/cases/${encodeURIComponent(selected.case_id)}/investigate`,
        { method: "POST" }
      );
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || `Investigator returned ${response.status}`);
      }
      setInvestigations((current) => ({ ...current, [selected.case_id]: payload }));
    } catch (investigationFailure) {
      setInvestigationError(String(investigationFailure.message || investigationFailure));
    } finally {
      setInvestigationLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="state-screen">
        <div className="state-card">
          <span className="state-card__eyebrow">Riskseer</span>
          <h1>Loading priority queue...</h1>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="state-screen">
        <div className="state-card state-card--error">
          <span className="state-card__eyebrow">Backend Connection</span>
          <h1>Could not load live case data</h1>
          <p>
            Start the API on <strong>{API_BASE}</strong> and make sure
            <strong> /api/cases</strong> returns JSON.
          </p>
          <code>{error}</code>
        </div>
      </div>
    );
  }

  if (!selected && casesWithRelations.length === 0) {
    return (
      <div className="state-screen">
        <div className="state-card">
          <span className="state-card__eyebrow">Riskseer</span>
          <h1>No cases returned from the backend.</h1>
        </div>
      </div>
    );
  }

  const contradictionTone =
    selected?.response_posture === "ESCALATE"
      ? "danger"
      : selected?.response_posture === "VERIFY_BEFORE_PROCEEDING"
      ? "warning"
      : "default";

  const tabs = [
    { id: "decision", label: "Decision" },
    { id: "chain", label: "Chain" },
    { id: "evidence", label: "Evidence" },
    { id: "investigator", label: "AI Investigator" },
  ];

  return (
    <div className={`app-shell ${activePage === "landing" ? "app-shell--landing" : ""}`}>
      {activePage !== "landing" ? (
        <header className="app-masthead">
          <div className="app-masthead__copy">
            <span className="hero__kicker">Riskseer Command Surface</span>
            <h1>Make the risky call easier to see.</h1>
            <p>
              Select a case from the queue, then dive into the action, chain, and evidence.
            </p>
          </div>
          <div className="app-masthead__stats">
            <StatCard
              label="Cases in view"
              value={filteredCases.length}
              detail={`${activeCount} active, ${watchCount} watch, ${closedCount} history`}
            />
            <StatCard
              label="Needs action now"
              value={stopCount + escalateCount + verifyCount}
              detail="Stop, escalate, and verify cases combined"
            />
            <StatCard
              label="Current focus"
              value={selected ? `Case ${selected.case_id}` : "None"}
              detail={
                selected
                  ? selected.nowState.command
                  : "Select a case from the queue to review it"
              }
            />
          </div>
        </header>
      ) : null}

      <section className="workspace-nav">
        <WorkspacePageButton
          active={activePage === "landing"}
          label="Landing"
          detail="Immediate attention"
          onClick={() => navigateToPage("landing")}
        />
        <WorkspacePageButton
          active={activePage === "queue"}
          label="Queue"
          detail="Click a case to review it"
          onClick={() => navigateToPage("queue")}
        />
      </section>
      {activePage === "landing" ? (
        <LandingPage
          spotlightCase={spotlightCase}
          riskierCases={riskierCases}
          saferCases={saferCases}
          stopCount={stopCount}
          escalateCount={escalateCount}
          verifyCount={verifyCount}
          monitorActiveCount={monitorActiveCount}
          onOpenQueue={openTopCaseInQueue}
        />
      ) : null}

      {activePage === "queue" ? (
        <>
          <section className="filter-shell">
            <div className="filter-shell__header">
              <span className="queue__eyebrow">Filters</span>
              <p>Use the main filters first. Open advanced filters only if you need to narrow further.</p>
            </div>
            <div className="queue-toolbar">
              <div className="queue-toolbar__summary">
                <strong>
                  Showing {filteredCases.length} of {casesWithRelations.length} cases
                </strong>
                <span>
                  Click any case to open its action, chain, and evidence.
                </span>
              </div>
            </div>
            <div className="filter-chip-row" aria-label="Active filters">
              {activeFilterChips.length > 0 ? (
                activeFilterChips.map((chip) => (
                  <span key={chip} className="filter-chip">
                    {chip}
                  </span>
                ))
              ) : (
                <span className="filter-chip filter-chip--muted">No extra filters applied</span>
              )}
            </div>
            <div className="filter-grid filter-grid--main">
              <label className="filter-control">
                <span>Search</span>
                <input
                  type="text"
                  value={filters.search}
                  onChange={(event) =>
                    setFilters((current) => ({ ...current, search: event.target.value }))
                  }
                  placeholder="Case, ticket, asset, event"
                />
              </label>
              <label className="filter-control">
                <span>Status</span>
                <select
                  value={filters.status}
                  onChange={(event) =>
                    setFilters((current) => ({ ...current, status: event.target.value }))
                  }
                >
                  <option value="ALL">All statuses</option>
                  <option value="ACTIVE">Active ({statusCounts.ACTIVE || 0})</option>
                  <option value="INACTIVE">Not active ({statusCounts.INACTIVE || 0})</option>
                  <option value="CLOSED">History ({statusCounts.CLOSED || 0})</option>
                </select>
              </label>
              <label className="filter-control">
                <span>Action</span>
                <select
                  value={filters.posture}
                  onChange={(event) =>
                    setFilters((current) => ({ ...current, posture: event.target.value }))
                  }
                >
                  <option value="ALL">All actions</option>
                  <option value="HOLD_WORK">Stop now ({postureCounts.HOLD_WORK || 0})</option>
                  <option value="ESCALATE">Escalate now ({postureCounts.ESCALATE || 0})</option>
                  <option value="VERIFY_BEFORE_PROCEEDING">Verify now ({postureCounts.VERIFY_BEFORE_PROCEEDING || 0})</option>
                  <option value="MONITOR">Monitor ({postureCounts.MONITOR || 0})</option>
                </select>
              </label>
              <button type="button" className="filter-clear" onClick={resetFilters}>
                Clear filters
              </button>
            </div>
            <details className="system-details">
              <summary>Advanced filters</summary>
              <div className="system-details__body">
                <div className="filter-grid filter-grid--advanced">
                  <label className="filter-control">
                    <span>Urgency</span>
                    <select
                      value={filters.urgency}
                      onChange={(event) =>
                        setFilters((current) => ({ ...current, urgency: event.target.value }))
                      }
                    >
                      <option value="ALL">All urgency</option>
                      <option value="CRITICAL">Critical ({urgencyCounts.CRITICAL || 0})</option>
                      <option value="HIGH">High ({urgencyCounts.HIGH || 0})</option>
                      <option value="MODERATE">Moderate ({urgencyCounts.MODERATE || 0})</option>
                      <option value="LOW">Low ({urgencyCounts.LOW || 0})</option>
                    </select>
                  </label>
                  <label className="filter-control">
                    <span>Trend</span>
                    <select
                      value={filters.trend}
                      onChange={(event) =>
                        setFilters((current) => ({ ...current, trend: event.target.value }))
                      }
                    >
                      <option value="ALL">All trends</option>
                      <option value="WORSENING">Getting worse ({trendCounts.WORSENING || 0})</option>
                      <option value="IMPROVING">Getting better ({trendCounts.IMPROVING || 0})</option>
                      <option value="STABLE">Stable ({trendCounts.STABLE || 0})</option>
                      <option value="REACTIVATED">Active again ({trendCounts.REACTIVATED || 0})</option>
                      <option value="NEW">New ({trendCounts.NEW || 0})</option>
                    </select>
                  </label>
                  <label className="filter-control">
                    <span>Primary reason</span>
                    <select
                      value={filters.failureLayer}
                      onChange={(event) =>
                        setFilters((current) => ({ ...current, failureLayer: event.target.value }))
                      }
                    >
                      <option value="ALL">All primary reasons</option>
                      {availableFailureLayers.map((layer) => (
                        <option key={layer} value={layer}>
                          {titleCaseFromEnum(layer)} ({failureLayerCounts[layer] || 0})
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="filter-toggle">
                    <input
                      type="checkbox"
                      checked={filters.relatedOnly}
                      onChange={(event) =>
                        setFilters((current) => ({ ...current, relatedOnly: event.target.checked }))
                      }
                    />
                    <span>Only show linked cases</span>
                  </label>
                </div>
              </div>
            </details>
          </section>

          <section className="queue-page">
            <div className="queue queue--full">
              <div className="queue__header">
                <span className="queue__eyebrow">Priority Queue</span>
                <p>Review the cases most likely to be waved through by mistake.</p>
              </div>
              <section className="queue-presets">
                <QuickPresetButton
                  active={filters.status === "ACTIVE" && filters.posture === "HOLD_WORK"}
                  label="Stop now"
                  detail={`${stopCount} cases need work paused`}
                  onClick={() =>
                    setFilterPreset({
                      search: "",
                      status: "ACTIVE",
                      posture: "HOLD_WORK",
                      urgency: "ALL",
                      trend: "ALL",
                      failureLayer: "ALL",
                      relatedOnly: false,
                    })
                  }
                />
                <QuickPresetButton
                  active={filters.status === "ACTIVE" && filters.posture === "ESCALATE"}
                  label="Escalate now"
                  detail={`${escalateCount} cases need human review`}
                  onClick={() =>
                    setFilterPreset({
                      search: "",
                      status: "ACTIVE",
                      posture: "ESCALATE",
                      urgency: "ALL",
                      trend: "ALL",
                      failureLayer: "ALL",
                      relatedOnly: false,
                    })
                  }
                />
                <QuickPresetButton
                  active={
                    filters.status === "ACTIVE" &&
                    filters.posture === "VERIFY_BEFORE_PROCEEDING"
                  }
                  label="Verify now"
                  detail={`${verifyCount} cases need support checked first`}
                  onClick={() =>
                    setFilterPreset({
                      search: "",
                      status: "ACTIVE",
                      posture: "VERIFY_BEFORE_PROCEEDING",
                      urgency: "ALL",
                      trend: "ALL",
                      failureLayer: "ALL",
                      relatedOnly: false,
                    })
                  }
                />
                <QuickPresetButton
                  active={filters.status === "ALL" && filters.posture === "ALL"}
                  label="All cases"
                  detail={`${filteredCases.length} cases in the current view`}
                  secondary
                  onClick={resetFilters}
                />
              </section>
              <StableCasesSummary
                count={monitorActiveCount}
                onOpen={() =>
                  setFilterPreset({
                    search: "",
                    status: "ACTIVE",
                    posture: "MONITOR",
                    urgency: "ALL",
                    trend: "ALL",
                    failureLayer: "ALL",
                    relatedOnly: false,
                  })
                }
              />
              <div className="queue__list">
                {queueSections.map((section) => (
                  <QueueSection
                    key={section.title}
                    title={section.title}
                    detail={section.detail}
                    items={section.items}
                    selectedId={selected?.case_id}
                    onSelect={openCase}
                  />
                ))}
              </div>
            </div>
          </section>
        </>
      ) : null}

      {activePage === "case" ? (
      <section className="case-page">
        <main className="detail">
          {!selected ? (
            <section className="empty-results">
              <span className="state-card__eyebrow">No Case Selected</span>
              <h2>No case is available in the current view.</h2>
              <p>Open a case from the priority queue to review the action and evidence.</p>
            </section>
          ) : (
          <>
          <section className="case-actions-bar">
            <button
              type="button"
              className="selected-case-banner__back"
              onClick={() => navigateToPage("queue")}
            >
              Back to queue
            </button>
            <div className="case-tab-switcher" role="tablist" aria-label="Case detail sections">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab.id}
                  className={`case-actions-bar__button ${activeTab === tab.id ? "case-actions-bar__button--active" : ""}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </section>
          <section className="selected-case-banner selected-case-banner--compact">
            <div className="selected-case-banner__main">
              <div className="selected-case-banner__nav">
                <span className="selected-case-banner__eyebrow">Case</span>
              </div>
              <h2>Case {selected.case_id}</h2>
              <p className="selected-case-banner__summary">{selected.queueReason}</p>
              <div className="selected-case-banner__facts">
                <span>{buildQueueLocation(selected)}</span>
                <span>Last field activity {formatDateTime(selected.lastFieldActivityAt)}</span>
                <span>
                  {selected.relatedCases?.length || 0} linked case
                  {(selected.relatedCases?.length || 0) === 1 ? "" : "s"}
                </span>
              </div>
            </div>
            <div className="selected-case-banner__meta">
              <TonePill tone={selected.tone}>
                {selected.status === "ACTIVE" ? selected.urgency || "LOW" : selected.status}
              </TonePill>
              <TonePill tone="neutral">
                {titleCaseFromEnum(selected.response_posture)}
              </TonePill>
              <TonePill tone={selected.changeSummary.tone}>{selected.changeSummary.label}</TonePill>
            </div>
          </section>
          <Panel eyebrow="Recommended Action" title={selected.nowState.command} tone={contradictionTone}>
            <p className="panel-summary">{selected.escalationSummary}</p>
            <div className="decision-punchline">
              <div className="decision-punchline__item">
                <span className="decision-punchline__label">Why this needs action</span>
                <strong>{selected.nowState.decisionPunchline}</strong>
              </div>
              <div className="decision-punchline__item">
                <span className="decision-punchline__label">What could go wrong</span>
                <strong>{selected.nowState.damageLine}</strong>
              </div>
            </div>
            <div className="snapshot-grid snapshot-grid--compact">
              {selected.evidenceSnapshot.slice(0, 3).map((item) => (
                <div className="snapshot-card" key={`${item.label}-${item.value}`}>
                  <span className="snapshot-card__label">{item.label}</span>
                  <strong className="snapshot-card__value">{item.value}</strong>
                  <span className="snapshot-card__detail">{item.detail}</span>
                </div>
              ))}
            </div>
          </Panel>
          <section className="tab-shell">
            <div className="tab-panel">
              {activeTab === "decision" ? (
                <>
                  <Panel eyebrow="Decision" title={selected.actionTabMeta.title} tone={contradictionTone}>
                    <div className="triage-grid triage-grid--compact">
                      <ListBlock
                        title="What looks normal"
                        items={buildSpotlightLooksNormal(selected)}
                        emptyLabel="No routine-looking signals were returned."
                      />
                      <ListBlock
                        title={selected.actionTabMeta.weakTitle}
                        items={selected.weakSupport.length > 0 ? selected.weakSupport : selected.breaks.slice(0, 4)}
                        emptyLabel="Nothing obvious is weakening support right now."
                      />
                      <ListBlock
                        title="Next steps"
                        items={selected.actions.slice(0, 3)}
                        emptyLabel="No immediate actions were returned."
                      />
                    </div>
                  </Panel>
                  <DecisionDefensibilityPanel caseData={selected} />
                  <ResponsibilityIntegrityPanel caseData={selected} />
                </>
              ) : null}

              {activeTab === "chain" ? (
                <div className="system-stack">
                  <ResponsibilityIntegrityPanel caseData={selected} />
                  <Panel eyebrow="Chain Fit" title="How this case should be read" tone="default">
                    <div className="triage-grid triage-grid--compact">
                      <ListBlock
                        title="Operator call"
                        items={[
                          selected.nowState.command,
                          selected.nowState.decisionPunchline,
                        ]}
                        emptyLabel="No operator call was returned."
                      />
                      <ListBlock
                        title="Weakest chain point"
                        items={
                          selected.chainStory?.weakLayer
                            ? [
                                `${selected.chainStory.weakLayer.label}: ${titleCaseFromEnum(selected.chainStory.weakLayer.state)}`,
                                selected.chainStory.weakLayer.reason,
                              ]
                            : ["No weak chain point was returned by the backend."]
                        }
                        emptyLabel="No chain weakness was returned."
                      />
                      <ListBlock
                        title="What to do with it"
                        items={selected.actions.slice(0, 3)}
                        emptyLabel="No next steps were returned."
                      />
                    </div>
                  </Panel>
                </div>
              ) : null}

              {activeTab === "evidence" ? (
                <div className="system-stack">
                  <Panel eyebrow="Evidence" title="Evidence" tone="default">
                    <div className="evidence-list">
                      {selected.evidenceFeed.length === 0 ? (
                        <p className="list-block__empty">No evidence layers were returned for this case.</p>
                      ) : (
                        selected.evidenceFeed.map((item, index) => (
                          <EvidenceRow key={`${item.lane}-${index}`} item={item} />
                        ))
                      )}
                    </div>
                  </Panel>

                  <div className="signal-grid signal-grid--wide">
                    <StatCard
                      label="What support exists"
                      value={selected.supportStatus.value}
                      detail={selected.supportStatus.detail}
                    />
                    <StatCard
                      label="Ticket match"
                      value={selected.authorizationClarity.label}
                      detail={selected.authorizationClarity.detail}
                    />
                    <StatCard
                      label="Last update"
                      value={formatDateTime(selected.updated_at)}
                      detail={`${selected.event_count || 0} events, ${selected.ticket_count || 0} tickets`}
                    />
                  </div>
                  <Panel eyebrow="Linked context" title="Related cases" tone="default">
                    <RelatedCasesBlock items={selected.relatedCases || []} onSelect={openCase} />
                  </Panel>
                  <details className="system-details">
                    <summary>More evidence</summary>
                    <div className="system-details__body">
                      <div className="assessment-grid">
                        <Panel eyebrow="Area and timing" title="Area and timing checks" tone="default">
                          <ListBlock
                            title="What does not line up"
                            items={selected.alignment_assessment?.concerns || []}
                            emptyLabel="No alignment concerns were recorded."
                          />
                        </Panel>

                        <Panel
                          eyebrow="Missing or unclear evidence"
                          title={
                            selected.information_integrity_assessment?.summary ||
                            "Missing or unclear evidence"
                          }
                          tone="default"
                        >
                          <ListBlock
                            title="Missing or unclear evidence"
                            items={selected.information_integrity_assessment?.concerns || []}
                            emptyLabel="No missing-information concerns were recorded."
                          />
                        </Panel>

                        <Panel
                          eyebrow="Why this could be waved through"
                          title={
                            selected.behavioral_risk_assessment?.summary ||
                            "Why this could be waved through"
                          }
                          tone="default"
                        >
                          <ListBlock
                            title="Wave-through signals"
                            items={selected.behavioral_risk_assessment?.concerns || []}
                            emptyLabel="No wave-through signals were recorded."
                          />
                        </Panel>
                      </div>

                      <Panel eyebrow="Case context" title="Case context" tone="default">
                        <ListBlock
                          title="Lifecycle"
                          items={[selected.lifecycle.summary]}
                          emptyLabel="No lifecycle summary was returned."
                        />
                        {(selected.status === "INACTIVE" || selected.status === "CLOSED") ? (
                          <div className="action-grid">
                            <ListBlock
                              title={selected.status === "CLOSED" ? "Why it closed" : "Why it is not active"}
                              items={selected.lifecycle.whyClosed || []}
                              emptyLabel="No lifecycle reasons were returned."
                            />
                            <ListBlock
                              title="What would bring it back"
                              items={selected.lifecycle.reactivation || []}
                              emptyLabel="No reactivation triggers were returned."
                            />
                          </div>
                        ) : null}
                        <details className="system-details">
                          <summary>Timeline</summary>
                          <div className="system-details__body">
                            <div className="timeline">
                              {selected.timeline.length === 0 ? (
                                <p className="list-block__empty">No timeline events were available for this case.</p>
                              ) : (
                                selected.timeline.map((item, index) => (
                                  <TimelineItem
                                    key={`${item.kind}-${item.label}-${item.when || index}`}
                                    item={item}
                                    index={index}
                                  />
                                ))
                              )}
                            </div>
                          </div>
                        </details>
                      </Panel>
                    </div>
                  </details>
                </div>
              ) : null}

              {activeTab === "investigator" ? (
                <div className="system-stack">
                  <Panel
                    eyebrow="OpenAI Investigator"
                    title="Evidence-cited operator brief"
                    tone="default"
                  >
                    <p className="panel-summary">
                      Riskseer&apos;s backend decision is locked at{" "}
                      <strong>{titleCaseFromEnum(selected.decision_state)}</strong> with a{" "}
                      <strong>{titleCaseFromEnum(selected.response_posture)}</strong> posture.
                      The investigator can explain that result, but cannot change it.
                    </p>
                    <button
                      type="button"
                      className="stable-summary__button"
                      onClick={runInvestigation}
                      disabled={investigationLoading || STATIC_DEMO}
                    >
                      {STATIC_DEMO
                        ? "Investigator requires live API"
                        : investigationLoading
                        ? "Investigating..."
                        : "Run investigator"}
                    </button>
                    {investigationError ? (
                      <p className="list-block__empty">{investigationError}</p>
                    ) : null}
                  </Panel>

                  {investigations[selected.case_id] ? (
                    <Panel
                      eyebrow={`Model: ${investigations[selected.case_id].model}`}
                      title={investigations[selected.case_id].summary}
                      tone="default"
                    >
                      <div className="triage-grid triage-grid--compact">
                        <ListBlock
                          title="What looks normal"
                          items={(investigations[selected.case_id].what_looks_normal || []).map(
                            (item) => `${item.statement} [${item.citation_ids.join(", ")}]`
                          )}
                          emptyLabel="No normal-looking signals were identified."
                        />
                        <ListBlock
                          title="Weak support and unknowns"
                          items={[
                            ...(investigations[selected.case_id].weak_support || []),
                            ...(investigations[selected.case_id].unknowns || []),
                          ].map(
                            (item) => `${item.statement} [${item.citation_ids.join(", ")}]`
                          )}
                          emptyLabel="No weak or unknown support was identified."
                        />
                        <ListBlock
                          title="Recommended checks"
                          items={(investigations[selected.case_id].recommended_checks || []).map(
                            (item) => `${item.statement} [${item.citation_ids.join(", ")}]`
                          )}
                          emptyLabel="No additional checks were returned."
                        />
                      </div>
                    </Panel>
                  ) : null}
                </div>
              ) : null}
            </div>
          </section>
          </>
          )}
        </main>
      </section>
      ) : null}
    </div>
  );
}
