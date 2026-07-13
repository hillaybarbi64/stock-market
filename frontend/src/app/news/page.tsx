"use client";

import { useQuery } from "@tanstack/react-query";
import { Panel } from "@/components/ui/panel";
import { Sym } from "@/components/ui/num";
import { apiGet } from "@/lib/api";

interface Article {
  id: string;
  symbol: string;
  headline: string;
  summary: string | null;
  source: string | null;
  url: string | null;
  image: string | null;
  datetime: string | null;
}

interface NewsResponse {
  available: boolean;
  reason?: string;
  symbols: string[];
  articles: Article[];
}

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3.6e6);
  if (h < 1) return "לפני פחות משעה";
  if (h < 24) return `לפני ${h} שעות`;
  const d = Math.floor(h / 24);
  return `לפני ${d} ימים`;
}

export default function NewsPage() {
  const news = useQuery({
    queryKey: ["news"],
    queryFn: () => apiGet<NewsResponse>("/news"),
    refetchInterval: 300_000,
  });

  const data = news.data;

  return (
    <div className="mx-auto max-w-4xl space-y-3">
      <div className="flex items-baseline justify-between">
        <h1 className="t-h1">חדשות מהתיק</h1>
        {data?.symbols?.length ? (
          <span className="text-[11px] text-faint" dir="ltr">
            {data.symbols.join(" · ")}
          </span>
        ) : null}
      </div>

      {news.isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-24 rounded-xl skeleton" />
          ))}
        </div>
      ) : data && !data.available ? (
        <Panel title="מרכז החדשות" subtitle="Market News">
          <div className="py-8 text-center">
            <p className="t-h2">מרכז החדשות אינו מוגדר</p>
            <p className="mx-auto mt-2 max-w-md text-[12.5px] leading-relaxed text-muted">{data.reason}</p>
            <a
              href="https://finnhub.io/register"
              target="_blank"
              rel="noopener noreferrer"
              className="press mt-4 inline-flex rounded-md bg-accent px-4 py-1.5 text-[12.5px] font-medium text-accent-fg hover:opacity-90"
            >
              קבל מפתח חינמי ב-Finnhub
            </a>
          </div>
        </Panel>
      ) : !data?.articles.length ? (
        <Panel title="חדשות מהתיק" subtitle="Market News">
          <p className="py-8 text-center text-[12.5px] text-muted">
            אין חדשות עדכניות לנכסים בתיק כרגע. נבדק שוב אוטומטית כל 5 דקות.
          </p>
        </Panel>
      ) : (
        <div className="space-y-2.5">
          {data.articles.map((a) => (
            <a
              key={a.id}
              href={a.url ?? undefined}
              target="_blank"
              rel="noopener noreferrer"
              className="press widget block p-3.5 transition-colors hover:bg-hover"
            >
              <div className="flex gap-3.5">
                {a.image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={a.image}
                    alt=""
                    className="h-16 w-24 shrink-0 rounded-md object-cover"
                    loading="lazy"
                  />
                ) : null}
                <div className="min-w-0">
                  <div className="mb-1 flex items-center gap-2 text-[10.5px] text-faint">
                    <span className="tag tag--live">
                      <Sym>{a.symbol}</Sym>
                    </span>
                    {a.source && <span dir="ltr">{a.source}</span>}
                    <span>· {timeAgo(a.datetime)}</span>
                  </div>
                  <h2 className="text-[13.5px] font-semibold leading-snug text-fg">{a.headline}</h2>
                  {a.summary && (
                    <p className="mt-1 line-clamp-2 text-[12px] leading-relaxed text-muted">{a.summary}</p>
                  )}
                </div>
              </div>
            </a>
          ))}
          <p className="t-help pt-1 text-center">מקור: Finnhub · לחיצה על כתבה פותחת את המקור בלשונית חדשה.</p>
        </div>
      )}
    </div>
  );
}
