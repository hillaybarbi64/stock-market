/*
  Honest placeholder for pages whose phase hasn't been built yet.
  Never fake data — say exactly what will exist here and when.
*/
export function PhaseStub({
  title,
  phase,
  items,
}: {
  title: string;
  phase: number;
  items: string[];
}) {
  return (
    <div className="mx-auto mt-16 max-w-md">
      <div className="rounded-md border border-line bg-panel p-6">
        <h1 className="text-[15px] font-semibold">{title}</h1>
        <p className="mt-1 text-[12.5px] text-muted">
          העמוד ייבנה בשלב {phase} של תוכנית העבודה. הוא יכלול:
        </p>
        <ul className="mt-3 space-y-1.5 text-[12.5px] text-muted">
          {items.map((item) => (
            <li key={item} className="flex gap-2">
              <span className="mt-[7px] size-1 shrink-0 rounded-full bg-faint" aria-hidden />
              {item}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
