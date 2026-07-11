interface StepBarProps {
  current: number
  total: number
}

export function StepBar({ current, total }: StepBarProps) {
  return (
    <div className="mb-8 flex gap-1.5">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`h-1 flex-1 rounded-full transition-colors duration-300 ${
            i < current ? "bg-foreground" : "bg-border"
          }`}
        />
      ))}
    </div>
  )
}
