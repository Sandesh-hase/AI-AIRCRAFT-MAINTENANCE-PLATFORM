export default function PanelCard({ title, subtitle, children, accent = 'cyan', badge = null }) {
  return (
    <section className={`panel-card panel-${accent}`}>
      <div className="panel-head">
        <div>
          <h3>{title}</h3>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        {badge || null}
      </div>
      <div className="panel-body">{children}</div>
    </section>
  );
}
