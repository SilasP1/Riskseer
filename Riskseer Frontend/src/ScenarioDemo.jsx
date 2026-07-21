import { useMemo, useState } from "react";
import { DEMO_SCENARIOS } from "./demoScenarios";
import "./ScenarioDemo.css";

function Icon({ name }) {
  const paths = {
    ticket: <path d="M5 7.5h14M7.5 4v7M16.5 4v7M7 15h4M7 18h7" />,
    sensor: <><circle cx="12" cy="12" r="2" /><path d="M7.8 7.8a6 6 0 0 0 0 8.4M16.2 7.8a6 6 0 0 1 0 8.4M4.6 4.6a10.5 10.5 0 0 0 0 14.8M19.4 4.6a10.5 10.5 0 0 1 0 14.8" /></>,
    layers: <><path d="m4 8 8-4 8 4-8 4-8-4Z" /><path d="m4 12 8 4 8-4M4 16l8 4 8-4" /></>,
    arrow: <path d="M5 12h13M14 7l5 5-5 5" />,
    map: <><path d="m4 6 5-2 6 2 5-2v14l-5 2-6-2-5 2V6Z" /><path d="M9 4v14M15 6v14" /></>,
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
        <path className="map-road" d="M0 402H820" />
        <path className="map-road-edge" d="M0 360H820" />
        <rect className="map-building" x="282" y="152" width="174" height="92" rx="4" />
        <rect className="map-container" x="504" y="146" width="74" height="30" rx="3" />
        <rect className="map-container" x="504" y="188" width="74" height="30" rx="3" />
        <rect className="map-container" x="504" y="230" width="74" height="30" rx="3" />
        <path className="map-fence" d="M182 348 210 104h444l36 244H182Z" />
        <path className="map-gate" d="M182 286h45" />
        <text className="map-label" x="302" y="202">EQUIPMENT STORAGE</text>
        <text className="map-minor-label" x="42" y="394">CEDAR ACCESS ROAD</text>
        <text className="map-minor-label" x="500" y="128">MATERIAL ROW</text>
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

  const activate = (selection) => (event) => {
    if (event.type === "keydown" && !["Enter", " "].includes(event.key)) return;
    if (event.type === "keydown") event.preventDefault();
    onSelect(selection);
  };

  return (
    <div className="demo-map-shell">
      <div className="demo-map-toolbar">
        <div>
          <span>Fictional site plan</span>
          <strong>{scenario.location}</strong>
        </div>
        <div className="demo-map-time">
          <span>Scenario time</span>
          <strong>{scenario.time}</strong>
        </div>
      </div>
      <div className="demo-map-stage">
        <svg
          className="demo-map"
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
                <g className="map-sensor" key={sensor.id} transform={`translate(${sensor.x} ${sensor.y})`}>
                  <circle r="8" />
                  <circle r="2.5" />
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
          {scenario.mode === "excavation" ? <><span><i className="legend-line legend-line--gas" />Gas</span><span><i className="legend-line legend-line--water" />Water</span></> : null}
          <span><i className="legend-zone" />Context zone</span>
          <span><i className="legend-sensor" />Thistle</span>
          <span><i className="legend-alert" />Detection</span>
        </div>
      </div>
    </div>
  );
}

function ContextPanel({ scenario, selected, selectedAlert, onSelectAlert }) {
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
            <span>811 / site record</span>
            <h2>{scenario.ticket.id}</h2>
          </div>
        </div>
        <dl className="demo-context-list">
          <div><dt>Designated scope</dt><dd>{scenario.ticket.scope}</dd></div>
          <div><dt>Context window</dt><dd>{scenario.ticket.window}</dd></div>
          <div><dt>Map relationship</dt><dd>The highlighted polygon is the area this record supports.</dd></div>
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

      <div className={`demo-action demo-action--${selectedAlert.priority.toLowerCase()}`}>
        <span>Recommended operator response</span>
        <strong>{selectedAlert.action}</strong>
        <p>Decision support only. A human remains responsible for the field response.</p>
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

  const selectedAlert =
    scenario.alerts.find((alert) => alert.id === selected.id) || scenario.alerts[0];

  const selectScenario = (id) => {
    const nextScenario = DEMO_SCENARIOS.find((item) => item.id === id) || DEMO_SCENARIOS[0];
    setScenarioId(nextScenario.id);
    setSelected({ type: "alert", id: nextScenario.selectedAlertId });
    setLayers({ ticket: true, assets: true, thistle: true });
  };
  const selectAlert = (id) => setSelected({ type: "alert", id });

  return (
    <div className="demo-app">
      <header className="demo-header">
        <div className="demo-brand">
          <span className="demo-brand__mark">R</span>
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
                aria-selected={item.id === scenario.id}
                className={item.id === scenario.id ? "demo-scenario-tab--active" : ""}
                onClick={() => selectScenario(item.id)}
              >
                <span>0{index + 1}</span>
                <strong>{item.label}</strong>
                <small>{item.shortLabel}</small>
              </button>
            ))}
          </div>
        </section>

        <section className="demo-scenario-summary">
          <div>
            <StateBadge tone={scenario.statusTone}>{scenario.status}</StateBadge>
            <h2>{scenario.headline}</h2>
            <p>{scenario.summary}</p>
          </div>
          <div className="demo-flow" aria-label="System flow">
            <span><Icon name="sensor" />Thistle detects</span>
            <i>→</i>
            <span><Icon name="ticket" />Context aligns</span>
            <i>→</i>
            <span><strong>R</strong>Riskseer interprets</span>
          </div>
        </section>

        <section className="demo-workspace">
          <aside className="demo-event-rail">
            <div className="demo-event-rail__header">
              <span className="demo-kicker">Signal sequence</span>
              <span>{scenario.sequence.length} events</span>
            </div>
            <div className="demo-event-list">
              <button
                type="button"
                className={selected.type === "ticket" ? "demo-event--selected" : ""}
                onClick={() => setSelected({ type: "ticket", id: scenario.ticket.id })}
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
                ["ticket", scenario.mode === "excavation" ? "811 zone" : "Site perimeter"],
                ["assets", "Underground assets"],
                ["thistle", "Thistle signals"],
              ].map(([key, label]) => (
                <label key={key} className={!scenario.assets.length && key === "assets" ? "demo-layer--disabled" : ""}>
                  <input
                    type="checkbox"
                    checked={layers[key]}
                    disabled={!scenario.assets.length && key === "assets"}
                    onChange={(event) => setLayers((current) => ({ ...current, [key]: event.target.checked }))}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
            <DemoMap scenario={scenario} selected={selected} onSelect={setSelected} layers={layers} />
          </div>

          <ContextPanel
            scenario={scenario}
            selected={selected}
            selectedAlert={selectedAlert}
            onSelectAlert={selectAlert}
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
