export function PolicyPdfFrame({ source, title, page = 1 }: { source: string; title: string; page?: number }) {
  return (
    <iframe
      src={source + "#page=" + page}
      title={title}
      className="min-h-[calc(100dvh-10.5rem)] w-full flex-1 rounded-xl border-0 bg-white"
    />
  )
}
