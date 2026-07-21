import { useMemo, useState } from "react";
import { DEMO_SCENARIOS } from "./demoScenarios";
import RiskseerMark from "./RiskseerMark";
import "./ScenarioDemo.css";

function Icon({ name }) {
  const paths = {
    ticket: <path d="M5 7.5h14M7.5 4v7M16.5 4v7M7 15h4M7 18h7" />,
    sensor: <><circle cx="12" cy="12" r="2" /><path d="M7.8 7.8a6 6 0 0 0 0 8.4M16.2 7.8a6 6 0 0 1 0 8.4M4.6 4.6a10.5 10.5 0 0 0 0 14.8M19.4 4.6a10.5 10.5 0 0 1 0 14.8" /></>,
    layers: <><path d="m4 8 8-4 8 4-8 4-8-4Z" /><path d="m4 12 8 4 8-4M4 16l8 4 8-4" /></>,
    arrow: <path d="M5 12h13M14 7l5 5-5 5" />,
    map: <><path d="m4 6 5-2 6 2 5-2v14l-5 2-6-2-5 2V6Z" /><path d="M9 4v14M15 6v14" /></>,
    camera: <><path d="M4 7h11v10H4zM15 10l5-3v10l-5-3" /><circle cx="9.5" cy="12" r="2.5" /></>,
    check: <path d="m5 12 4 4L19 6" />,
  };

  return (
    <svg className="demo-icon" viewBox="0 0 24 24" aria-hidden="true">
      {paths[name] || paths.map}
    </svg>
  );
}

function StateBadge({ tone, children }) {
  return <span className={`demo-state demo-state--${tone}`}>{children}</span>;
}

function MapBase({ mode }) {
  if (mode === "security") {
    return (
      <>
        <rect className="map-ground" x="22" y="24" width="776" height="432" rx="18" />
        <rect className="map-security-site" x="110" y="56" width="594" height="330" rx="8" />
        <path className="map-road" d="M0 422H820" />
        <path className="map-road-edge" d="M0 382H820" />
        <path className="map-fence" d="M110 386V56h594v330H110Z" />
        <path className="map-gate" d="M168 386h74" />
        <path className="map-access-lane" d="M205 386C214 338 262 310 318 302" />
        <g className="map-equipment-row">
          <rect x="518" y="112" width="118" height="38" rx="4" />
          <rect x="518" y="164" width="118" height="38" rx="4" />
          <rect x="518" y="216" width="118" height="38" rx="4" />
        </g>
        <g className="map-security-trailer" transform="translate(286 278)">
          <path className="map-security-trailer__hitch" d="M0 21h-18l-12 9" />
          <rect className="map-security-trailer__body" x="0" y="0" width="94" height="44" rx="5" />
          <rect className="map-security-trailer__solar" x="8" y="7" width="35" height="30" rx="2" />
          <rect className="map-security-trailer__solar" x="51" y="7" width="35" height="30" rx="2" />
          <circle className="map-security-trailer__mast" cx="47" cy="22" r="9" />
          <path className="map-security-trailer__camera" d="M47 13V-18l15-8" />
          <circle className="map-security-trailer__camera-head" cx="64" cy="-27" r="6" />
        </g>
        <text className="map-minor-label" x="333" y="346">MOBILE CAMERA / PTZ-01</text>
        <text className="map-minor-label" x="520" y="96">EQUIPMENT LAYDOWN</text>
        <text className="map-minor-label" x="28" y="414">CEDAR ACCESS ROAD</text>
        <text className="map-minor-label" x="176" y="374">SITE GATE</text>
      </>
    );
  }

  return (
    <>
      <rect className="map-ground" x="22" y="24" width="776" height="432" rx="18" />
      <rect className="map-parcel" x="64" y="56" width="174" height="112" rx="5" />
      <rect className="map-parcel" x="252" y="56" width="164" height="112" rx="5" />
      <rect className="map-parcel" x="430" y="56" width="160" height="112" rx="5" />
      <rect className="map-parcel" x="604" y="56" width="152" height="112" rx="5" />
      <rect className="map-parcel" x="64" y="350" width="174" height="72" rx="5" />
      <rect className="map-parcel" x="252" y="350" width="164" height="72" rx="5" />
      <rect className="map-parcel" x="430" y="350" width="160" height="72" rx="5" />
      <rect className="map-parcel" x="604" y="350" width="152" height="72" rx="5" />
      <rect className="map-road-fill" x="22" y="176" width="776" height="164" />
      <path className="map-road-center" d="M22 258H798" />
      <path className="map-sidewalk" d="M22 184H798M22 332H798" />
      <text className="map-label" x="350" y="246">CEDAR WAY</text>
      <text className="map-minor-label" x="86" y="92">PARCEL 12</text>
      <text className="map-minor-label" x="274" y="92">PARCEL 14</text>
      <text className="map-minor-label" x="452" y="92">PARCEL 16</text>
      <text className="map-minor-label" x="626" y="92">PARCEL 18</text>
    </>
  );
}

function DemoMap({ scenario, selected, onSelect, layers }) {
  const ticketSelected = selected.type === "ticket";
  const selectedAlert = scenario.alerts.find((alert) => alert.id === selected.id);
  const activeSensorId = selectedAlert?.sensor?.replace("Thistle ", "");
  const isSecurity = scenario.mode === "security";

  const activate = (selection) => (event) => {
    if (event.type === "keydown" && !["Enter", " "].includes(event.key)) return;
    if (event.type === "keydown") event.preventDefault();
    onSelect(selection);
  };

  return (
    <div className={`demo-map-shell demo-map-shell--${scenario.mode}`}>
      <div className="demo-map-toolbar">
        <div>
          <span>Fictional site plan</span>
          <strong>{scenario.location}</strong>
        </div>
        <div className="demo-map-instruction">
          <Icon name="map" />
          <span>{isSecurity ? "Select the monitored area or a queued event" : "Select the blue zone or a detection"}</span>
        </div>
        <div className="demo-map-time">
          <span>Scenario time</span>
          <strong>{scenario.time}</strong>
        </div>
      </div>
      <div className="demo-map-stage">
        <svg
          className={`demo-map demo-map--${scenario.mode}`}
          viewBox="0 0 820 480"
          role="img"
          aria-label={`${scenario.location} interactive demo map`}
        >
          <defs>
            <pattern id="map-grid" width="24" height="24" patternUnits="userSpaceOnUse">
              <path d="M24 0H0V24" fill="none" stroke="currentColor" strokeWidth="0.5" />
            </pattern>
            <filter id="alert-shadow" x="-60%" y="-60%" width="220%" height="220%">
              <feDropShadow dx="0" dy="3" stdDeviation="4" floodOpacity="0.22" />
            </filter>
          </defs>

          <MapBase mode={scenario.mode} />
          <rect className="map-grid" x="22" y="24" width="776" height="432" rx="18" />

          {isSecurity && layers.assets ? (
            <g className="map-camera-cue" aria-hidden="true">
              <path className="map-camera-coverage" d="M350 251 690 142 690 354Z" />
              {selectedAlert?.requiresConfirmation ? (
                <>
                  <path className="map-camera-cue-line" d={`M350 251L${selectedAlert.x} ${selectedAlert.y}`} />
                  <g className="map-camera-cue-label" transform="translate(406 218)">
                    <rect width="86" height="22" rx="11" />
                    <text x="43" y="14">CAMERA CUED</text>
                  </g>
                </>
              ) : null}
            </g>
          ) : null}

          {layers.assets
            ? scenario.assets.map((asset) => (
                <g key={asset.id}>
                  <path className={`map-asset map-asset--${asset.kind}`} d={asset.path} />
                  <text className={`map-asset-label map-asset-label--${asset.kind}`} x="704" y={asset.kind === "water" ? 190 : asset.kind === "gas" ? 265 : 321}>
                    {asset.label}
                  </text>
                </g>
              ))
            : null}

          {layers.ticket ? (
            <g
              className={`map-ticket ${ticketSelected ? "map-ticket--selected" : ""}`}
              role="button"
              tabIndex="0"
              aria-label={`Select context ${scenario.ticket.id}`}
              onClick={activate({ type: "ticket", id: scenario.ticket.id })}
              onKeyDown={activate({ type: "ticket", id: scenario.ticket.id })}
            >
              <polygon points={scenario.ticket.polygon} />
              <g transform={`translate(${scenario.ticket.center[0] - 58} ${scenario.ticket.center[1] - 72})`}>
                <rect width="116" height="25" rx="4" />
                <text x="58" y="16">{scenario.ticket.id}</text>
              </g>
            </g>
          ) : null}

          {layers.thistle
            ? scenario.sensors.map((sensor) => (
                <g
                  className={`map-sensor ${isSecurity ? "map-sensor--security" : ""} ${sensor.id === activeSensorId ? "map-sensor--active" : ""}`}
                  key={sensor.id}
                  transform={`translate(${sensor.x} ${sensor.y})`}
                >
                  {isSecurity ? <circle className="map-sensor__range" r="18" /> : null}
                  <circle className="map-sensor__body" r="8" />
                  <circle className="map-sensor__core" r="2.5" />
                  <text x="11" y="4">{sensor.id}</text>
                </g>
              ))
            : null}

          {layers.thistle
            ? scenario.alerts.map((alert) => {
                const isSelected = selected.type === "alert" && selected.id === alert.id;
                return (
                  <g
                    key={alert.id}
                    className={`map-alert map-alert--${alert.priority.toLowerCase()} ${isSelected ? "map-alert--selected" : ""}`}
                    transform={`translate(${alert.x} ${alert.y})`}
                    role="button"
                    tabIndex="0"
                    aria-label={`Select Thistle alert ${alert.id}: ${alert.title}`}
                    onClick={activate({ type: "alert", id: alert.id })}
                    onKeyDown={activate({ type: "alert", id: alert.id })}
                  >
                    <circle className="map-alert__pulse" r="25" />
                    <circle className="map-alert__core" r="12" filter="url(#alert-shadow)" />
                    <path d="M-4 0h8M0-4v8" />
                    {isSelected ? (
                      <g className="map-alert__label" transform="translate(18 -18)">
                        <rect width="122" height="34" rx="5" />
                        <text x="10" y="14">{alert.id}</text>
                        <text x="10" y="26">{alert.action}</text>
                      </g>
                    ) : null}
                  </g>
                );
              })
            : null}
        </svg>

        <div className="demo-map-legend" aria-label="Map legend">
          {isSecurity ? (
            <>
              <span><i className="legend-zone" />Monitored area</span>
              <span><i className="legend-sensor" />Thistle cue node</span>
              <span><i className="legend-camera" />Mobile camera</span>
              <span><i className="legend-alert" />Queued event</span>
            </>
          ) : (
            <>
              <span><i className="legend-line legend-line--gas" />Gas</span>
              <span><i className="legend-line legend-line--water" />Water</span>
              <span><i className="legend-zone" />811 zone</span>
              <span><i className="legend-sensor" />Thistle</span>
              <span><i className="legend-alert" />Detection</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ContextPanel({ scenario, selected, selectedAlert, onSelectAlert, confirmation, onConfirm }) {
  if (selected.type === "ticket") {
    return (
      <aside className="demo-inspector">
        <div className="demo-inspector__header">
          <span className="demo-kicker">Operational context</span>
          <StateBadge tone="context">{scenario.ticket.status}</StateBadge>
        </div>
        <div className="demo-inspector__title">
          <Icon name="ticket" />
          <div>
            <span>{scenario.mode === "security" ? "Temporary security record" : "811 / site record"}</span>
            <h2>{scenario.ticket.id}</h2>
          </div>
        </div>
        <dl className="demo-context-list">
          <div><dt>Designated scope</dt><dd>{scenario.ticket.scope}</dd></div>
          <div><dt>Context window</dt><dd>{scenario.ticket.window}</dd></div>
          <div>
            <dt>Map relationship</dt>
            <dd>{scenario.mode === "security" ? "The highlighted area shows the Thistle cue perimeter and its camera handoff." : "The highlighted polygon is the area this record supports."}</dd>
          </div>
        </dl>
        <div className="demo-inspector__prompt">
          <Icon name="sensor" />
          <div>
            <strong>Now select a Thistle alert</strong>
            <p>Riskseer compares each detection with this context instead of treating every signal as equally urgent.</p>
          </div>
        </div>
        <div className="demo-inspector__alert-links">
          {scenario.alerts.map((alert) => (
            <button key={alert.id} type="button" onClick={() => onSelectAlert(alert.id)}>
              <span>{alert.id}</span>
              <strong>{alert.title}</strong>
              <Icon name="arrow" />
            </button>
          ))}
        </div>
      </aside>
    );
  }

  return (
    <aside className="demo-inspector">
      <div className="demo-inspector__header">
        <span className="demo-kicker">Riskseer interpretation</span>
        <StateBadge tone={selectedAlert.priority === "HIGH" ? "high" : "low"}>
          {selectedAlert.priority} PRIORITY
        </StateBadge>
      </div>
      <div className="demo-inspector__title">
        <Icon name="sensor" />
        <div>
          <span>{selectedAlert.id} · {selectedAlert.time}</span>
          <h2>{selectedAlert.title}</h2>
        </div>
      </div>
      <p className="demo-inspector__summary">{selectedAlert.detail}</p>

      <div className="demo-comparison" aria-label="Context comparison">
        {selectedAlert.comparisons.map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>

      {selectedAlert.requiresConfirmation ? (
        <div className="demo-confirmation">
          <div className="demo-confirmation__cue">
            <span className="demo-confirmation__camera"><Icon name="camera" /></span>
            <div>
              <span className="demo-kicker">Verification handoff</span>
              <strong>{selectedAlert.verification.source} → {selectedAlert.verification.target}</strong>
              <small>Simulated camera cue · no live video connected</small>
            </div>
            <StateBadge tone="context">{selectedAlert.verification.status}</StateBadge>
          </div>
          <div className="demo-confirmation__prompt">
            <span className="demo-kicker">Operator confirmation</span>
            <strong>What does the camera check show?</strong>
          </div>
          <div className="demo-confirmation__options" role="group" aria-label="Classify queued activity">
            {[
              ["authorized", "Expected / authorized"],
              ["unexpected", "Unexpected activity"],
              ["unclear", "Camera inconclusive"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={confirmation === value ? "demo-confirmation__selected" : ""}
                aria-pressed={confirmation === value}
                onClick={() => onConfirm(value)}
              >
                {label}
              </button>
            ))}
          </div>
          {confirmation ? (
            <div className={`demo-confirmation__result demo-confirmation__result--${confirmation}`} aria-live="polite">
              <strong>{confirmation === "authorized" ? "Verified expected" : confirmation === "unexpected" ? "Verified unexpected" : "Camera inconclusive"}</strong>
              <span>
                {confirmation === "authorized"
                  ? "Log the event and return the site to monitoring."
                  : confirmation === "unexpected"
                  ? "Escalate through the site's response plan."
                  : "Keep the event queued and request another verification source."}
              </span>
              <small>Demo only · no response was sent</small>
            </div>
          ) : null}
          <p className="demo-confirmation__boundary">Riskseer supplies context and records the choice. The operator owns the classification and response.</p>
        </div>
      ) : (
        <div className={`demo-action demo-action--${selectedAlert.priority.toLowerCase()}`}>
          <span>Recommended operator response</span>
          <strong>{selectedAlert.action}</strong>
          <p>Decision support only. A human remains responsible for the field response.</p>
        </div>
      )}

      <div className="demo-reasoning">
        <span className="demo-kicker">Why this result</span>
        <ol>
          {selectedAlert.reasons.map((reason) => (
            <li key={reason}>
              <Icon name="check" />
              <span>{reason}</span>
            </li>
          ))}
        </ol>
      </div>
    </aside>
  );
}

export default function ScenarioDemo() {
  const [scenarioId, setScenarioId] = useState(DEMO_SCENARIOS[0].id);
  const scenario = useMemo(
    () => DEMO_SCENARIOS.find((item) => item.id === scenarioId) || DEMO_SCENARIOS[0],
    [scenarioId]
  );
  const [selected, setSelected] = useState({ type: "alert", id: scenario.selectedAlertId });
  const [layers, setLayers] = useState({ ticket: true, assets: true, thistle: true });
  const [confirmation, setConfirmation] = useState(null);

  const selectedAlert =
    scenario.alerts.find((alert) => alert.id === selected.id) || scenario.alerts[0];

  const selectScenario = (id) => {
    const nextScenario = DEMO_SCENARIOS.find((item) => item.id === id) || DEMO_SCENARIOS[0];
    setScenarioId(nextScenario.id);
    setSelected({ type: "alert", id: nextScenario.selectedAlertId });
    setLayers({ ticket: true, assets: true, thistle: true });
    setConfirmation(null);
  };
  const selectItem = (item) => {
    setSelected(item);
    setConfirmation(null);
  };
  const selectAlert = (id) => selectItem({ type: "alert", id });
  const navigateScenarios = (event, index) => {
    const keyMoves = {
      ArrowRight: (index + 1) % DEMO_SCENARIOS.length,
      ArrowLeft: (index - 1 + DEMO_SCENARIOS.length) % DEMO_SCENARIOS.length,
      Home: 0,
      End: DEMO_SCENARIOS.length - 1,
    };
    const nextIndex = keyMoves[event.key];
    if (nextIndex === undefined) return;
    event.preventDefault();
    selectScenario(DEMO_SCENARIOS[nextIndex].id);
    event.currentTarget.parentElement.children[nextIndex].focus();
  };

  const selectionAnnouncement =
    selected.type === "ticket"
      ? `Selected context record ${scenario.ticket.id}`
      : `Selected Thistle alert ${selectedAlert.id}: ${selectedAlert.title}`;

  return (
    <div className="demo-app">
      <header className="demo-header">
        <div className="demo-brand">
          <RiskseerMark className="demo-brand__mark" labelled />
          <div>
            <strong>Riskseer</strong>
            <span>Thistle + operational context</span>
          </div>
        </div>
        <div className="demo-header__label">
          <span className="demo-live-dot" />
          Guided system demo
        </div>
        <a href="https://github.com/SilasP1/Riskseer" target="_blank" rel="noreferrer">
          View repository <Icon name="arrow" />
        </a>
      </header>

      <main className="demo-main">
        <section className="demo-intro">
          <div>
            <span className="demo-kicker">Select a scenario</span>
            <h1>Watch field signals become decisions.</h1>
            <p>
              Explore how Thistle detections are interpreted against 811 and temporary-site context.
              Every location and record shown here is fictional.
            </p>
          </div>
          <div className="demo-scenario-tabs" role="tablist" aria-label="Demo scenarios">
            {DEMO_SCENARIOS.map((item, index) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                id={`demo-scenario-tab-${item.id}`}
                aria-controls="demo-scenario-panel"
                aria-selected={item.id === scenario.id}
                tabIndex={item.id === scenario.id ? 0 : -1}
                className={item.id === scenario.id ? "demo-scenario-tab--active" : ""}
                onClick={() => selectScenario(item.id)}
                onKeyDown={(event) => navigateScenarios(event, index)}
              >
                <span>0{index + 1}</span>
                <strong>{item.label}</strong>
                <small>{item.shortLabel}</small>
              </button>
            ))}
          </div>
        </section>

        <ol className="demo-guide" aria-label="How to use this demo">
          <li>
            <span>1</span>
            <div><strong>Choose a scenario</strong><small>Start with a field situation above.</small></div>
          </li>
          <li>
            <span>2</span>
            <div><strong>Select context or a signal</strong><small>Click the blue zone or an alert marker.</small></div>
          </li>
          <li>
            <span>3</span>
            <div><strong>Review the interpretation</strong><small>See why Riskseer monitors, queues, or escalates.</small></div>
          </li>
        </ol>

        <section
          className="demo-scenario-summary"
          id="demo-scenario-panel"
          role="tabpanel"
          aria-labelledby={`demo-scenario-tab-${scenario.id}`}
        >
          <div>
            <StateBadge tone={scenario.statusTone}>{scenario.status}</StateBadge>
            <h2>{scenario.headline}</h2>
            <p>{scenario.summary}</p>
          </div>
          <div className="demo-flow" aria-label="System flow">
            {scenario.mode === "security" ? (
              <>
                <span><Icon name="sensor" />Thistle detects</span>
                <i>→</i>
                <span><RiskseerMark className="demo-flow__mark" />Riskseer checks</span>
                <i>→</i>
                <span><Icon name="camera" />Camera is cued</span>
                <i>→</i>
                <span><Icon name="check" />Operator confirms</span>
              </>
            ) : (
              <>
                <span><Icon name="sensor" />Thistle detects</span>
                <i>→</i>
                <span><Icon name="ticket" />811 context compares</span>
                <i>→</i>
                <span><RiskseerMark className="demo-flow__mark" />Riskseer interprets</span>
              </>
            )}
          </div>
        </section>

        <p className="demo-sr-only" aria-live="polite">{selectionAnnouncement}</p>

        <section className="demo-workspace">
          <aside className="demo-event-rail">
            <div className="demo-event-rail__header">
              <span className="demo-kicker">Signal sequence</span>
              <span>{scenario.sequence.length} events</span>
            </div>
            <div className="demo-event-list">
              <button
                type="button"
                aria-pressed={selected.type === "ticket"}
                className={selected.type === "ticket" ? "demo-event--selected" : ""}
                onClick={() => selectItem({ type: "ticket", id: scenario.ticket.id })}
              >
                <span className="demo-event__icon"><Icon name="ticket" /></span>
                <span className="demo-event__copy">
                  <small>Context record</small>
                  <strong>{scenario.ticket.id}</strong>
                  <em>{scenario.ticket.status} · select zone</em>
                </span>
              </button>
              {scenario.alerts.map((alert) => (
                <button
                  key={alert.id}
                  type="button"
                  aria-pressed={selected.type === "alert" && selected.id === alert.id}
                  className={selected.type === "alert" && selected.id === alert.id ? "demo-event--selected" : ""}
                  onClick={() => selectAlert(alert.id)}
                >
                  <span className={`demo-event__icon demo-event__icon--${alert.priority.toLowerCase()}`}><Icon name="sensor" /></span>
                  <span className="demo-event__copy">
                    <small>{alert.time} · {alert.sensor}</small>
                    <strong>{alert.title}</strong>
                    <em>{alert.priority} priority</em>
                  </span>
                </button>
              ))}
            </div>

            <div className="demo-timeline">
              <span className="demo-kicker">What happened</span>
              <ol>
                {scenario.sequence.map(([time, title, detail]) => (
                  <li key={`${time}-${title}`}>
                    <span>{time}</span>
                    <strong>{title}</strong>
                    <p>{detail}</p>
                  </li>
                ))}
              </ol>
            </div>
          </aside>

          <div className="demo-map-column">
            <div className="demo-layer-controls" aria-label="Map layers">
              <span><Icon name="layers" />Layers</span>
              {[
                ["ticket", scenario.mode === "excavation" ? "811 zone" : "Monitored area"],
                ["assets", scenario.mode === "excavation" ? "Underground assets" : "Camera cue"],
                ["thistle", scenario.mode === "excavation" ? "Thistle signals" : "Thistle cue nodes"],
              ].map(([key, label]) => (
                <label key={key} className={scenario.mode === "excavation" && !scenario.assets.length && key === "assets" ? "demo-layer--disabled" : ""}>
                  <input
                    type="checkbox"
                    checked={layers[key]}
                    disabled={scenario.mode === "excavation" && !scenario.assets.length && key === "assets"}
                    onChange={(event) => setLayers((current) => ({ ...current, [key]: event.target.checked }))}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
            <DemoMap scenario={scenario} selected={selected} onSelect={selectItem} layers={layers} />
          </div>

          <ContextPanel
            scenario={scenario}
            selected={selected}
            selectedAlert={selectedAlert}
            onSelectAlert={selectAlert}
            confirmation={confirmation}
            onConfirm={setConfirmation}
          />
        </section>
      </main>

      <footer className="demo-footer">
        <div>
          <strong>Guided scenario demo</strong>
          <p>Fixture interpretations are precomputed for a safe, repeatable public walkthrough.</p>
        </div>
        <p>The repository retains the working Riskseer engine, API, tests, and OpenAI investigator path.</p>
      </footer>
    </div>
  );
}
