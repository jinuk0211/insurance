import { NextRequest, NextResponse } from "next/server"
import { deriveUserKey } from "@/lib/user-key"
import { listQueryHistory, getQueryHistoryItem } from "@/lib/db/history"
import { z } from "zod"

const HistoryInput = z.object({
  phone: z.string().max(20).transform((value) => value.replace(/\D/g, "")).pipe(z.string().regex(/^01\d{8,9}$/)),
  birth: z.string().regex(/^\d{6}$/),
  id: z.string().uuid().optional(),
})

// POST { phone, birth }        → 해당 사용자의 조회 이력 요약 목록
// POST { phone, birth, id }    → 해당 이력 단건(복호화된 전체 결과)
export async function POST(req: NextRequest) {
  try {
    const parsed = HistoryInput.safeParse(await req.json())
    if (!parsed.success) {
      return NextResponse.json({ error: "조회 정보를 다시 확인해주세요." }, { status: 400 })
    }
    const { phone, birth, id } = parsed.data
    const userKey = deriveUserKey(phone, birth)

    if (id) {
      const data = await getQueryHistoryItem(id, userKey)
      if (!data) return NextResponse.json({ error: "이력을 찾을 수 없습니다." }, { status: 404 })
      return NextResponse.json({ data })
    }

    const items = await listQueryHistory(userKey)
    return NextResponse.json({ items })
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "서버 오류"
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
