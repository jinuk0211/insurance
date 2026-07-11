import { NextRequest, NextResponse } from "next/server"
import { saveSession } from "@/lib/session-store"
import { findRegisteredUser } from "@/lib/db/registered-user"
import { randomUUID } from "crypto"
import { z } from "zod"

const CheckUserInput = z.object({
  phoneNo: z.string().max(20).transform((value) => value.replace(/\D/g, "")).pipe(z.string().regex(/^01\d{8,9}$/)),
  birthDate: z.string().regex(/^\d{6}$/),
  userName: z.string().trim().min(1).max(50),
})

export async function POST(req: NextRequest) {
  try {
    const parsed = CheckUserInput.safeParse(await req.json())
    if (!parsed.success) {
      return NextResponse.json({ error: "입력 정보를 다시 확인해주세요." }, { status: 400 })
    }
    const { phoneNo, birthDate, userName } = parsed.data

    const existing = await findRegisteredUser(phoneNo, birthDate)

    if (existing) {
      const sessionId = randomUUID()
      await saveSession(sessionId, {
        baseParams: {
          organization: "0001",
          userName,
          birthDate,
          telecom: "0",
          phoneNo,
          authMethod: "1",
        },
        loginId: existing.id,
        loginPw: existing.pw,
        step: "done",
      })
      return NextResponse.json({ found: true, sessionId })
    }

    return NextResponse.json({ found: false })
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "서버 오류"
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
