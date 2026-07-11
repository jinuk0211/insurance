import { NextRequest, NextResponse } from "next/server"
import { codefPost } from "@/lib/codef-client"
import { getSession } from "@/lib/session-store"
import { saveQueryHistory } from "@/lib/db/history"
import { saveRegisteredUser } from "@/lib/db/registered-user"
import { z } from "zod"

const QueryConfirmInput = z.object({
  sessionId: z.string().uuid(),
  smsAuthNo: z.union([z.literal(""), z.string().regex(/^\d{4,8}$/)]).optional().default(""),
})

export async function POST(req: NextRequest) {
  try {
    const parsed = QueryConfirmInput.safeParse(await req.json())
    if (!parsed.success) {
      return NextResponse.json({ error: "인증 요청 정보를 다시 확인해주세요." }, { status: 400 })
    }
    const { sessionId, smsAuthNo } = parsed.data
    const session = await getSession(sessionId)
    if (!session) return NextResponse.json({ error: "세션 만료." }, { status: 404 })

    const authMethod = String(session.queryParams?.authMethod ?? session.baseParams.authMethod ?? "1")
    const isPass = authMethod === "1"
    if (!isPass && !smsAuthNo) {
      return NextResponse.json({ error: "SMS 인증번호를 입력해주세요." }, { status: 400 })
    }

    const params = {
      ...session.queryParams,
      smsAuthNo: isPass ? "" : smsAuthNo,
      simpleAuth: isPass ? "1" : "0",
      is2Way: true,
      twoWayInfo: session.queryTwoWayInfo,
    }

    const result = await codefPost("/v1/kr/insurance/0001/credit4u/contract-info", params)
    const code = result?.result?.code

    if (code === "CF-03002" || code === "CF-03003") return NextResponse.json({ status: "pending" })
    if (code === "CF-00000") {
      const loginId = session.loginId || session.finalId || session.regId || ""
      const loginPw = session.loginPw || session.finalPw || session.regPw || ""
      if (loginId && loginPw) {
        try {
          await saveRegisteredUser(
            String(session.baseParams.phoneNo),
            String(session.baseParams.birthDate),
            loginId,
            loginPw
          )
        } catch (e) {
          console.error("등록 사용자 저장 실패:", e instanceof Error ? e.message : e)
        }
      }
      try {
        await saveQueryHistory(session.baseParams, result?.data, sessionId)
      } catch (e) {
        console.error("조회 이력 저장 실패:", e instanceof Error ? e.message : e)
      }
      return NextResponse.json({ status: "success", data: result?.data })
    }

    return NextResponse.json({ status: "error", error: result?.result?.message, code }, { status: 400 })
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "서버 오류"
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
