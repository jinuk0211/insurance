import { NextRequest, NextResponse } from "next/server"
import { codefPost, rsaEncrypt } from "@/lib/codef-client"
import { getSession, saveSession } from "@/lib/session-store"
import { saveRegisteredUser } from "@/lib/db/registered-user"

export async function POST(req: NextRequest) {
  try {
    const { sessionId, emailAuthNo } = await req.json()
    const session = await getSession(sessionId)
    if (!session) return NextResponse.json({ error: "세션 만료." }, { status: 404 })

    const params = {
      ...session.baseParams,
      id: session.finalId || session.regId || "",
      password: rsaEncrypt(session.finalPw || session.regPw || ""),
      email: session.finalEmail || session.regEmail || "",
      emailAuthNo,
      is2Way: true,
      twoWayInfo: session.twoWayInfo,
    }

    const result = await codefPost("/v1/kr/insurance/0001/credit4u/register", params)
    const code = result?.result?.code

    if (code === "CF-00000" || code === "CF-03002") {
      const loginId = result?.data?.resLoginId || session.finalId || session.regId || ""
      const loginPw = session.finalPw || session.regPw || ""
      await saveRegisteredUser(session.baseParams.phoneNo as string, session.baseParams.birthDate as string, loginId, loginPw)
      await saveSession(sessionId, { step: "done", loginId, loginPw })
      return NextResponse.json({ status: "registered", sessionId, loginId })
    }

    return NextResponse.json({ status: "error", error: result?.result?.message, code }, { status: 400 })
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "서버 오류"
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
