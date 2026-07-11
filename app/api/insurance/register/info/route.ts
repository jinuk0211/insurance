import { NextRequest, NextResponse } from "next/server"
import { codefPost, rsaEncrypt } from "@/lib/codef-client"
import { getSession, saveSession } from "@/lib/session-store"
import { saveRegisteredUser } from "@/lib/db/registered-user"

export async function POST(req: NextRequest) {
  try {
    const { sessionId, id, pw, email } = await req.json()
    const session = await getSession(sessionId)
    if (!session) return NextResponse.json({ error: "세션 만료." }, { status: 404 })
    if (!id || !pw || !email) return NextResponse.json({ error: "모든 항목을 입력해주세요." }, { status: 400 })

    await saveSession(sessionId, { finalId: id, finalPw: pw, finalEmail: email })

    const params = {
      ...session.baseParams,
      id,
      password: rsaEncrypt(pw),
      email,
      is2Way: true,
      twoWayInfo: session.twoWayInfo,
    }

    const result = await codefPost("/v1/kr/insurance/0001/credit4u/register", params)
    const code = result?.result?.code
    const extraInfo = result?.data?.extraInfo || {}

    if (extraInfo.reqEmailAuthNo !== undefined || code === "CF-03002") {
      await saveSession(sessionId, {
        twoWayInfo: {
          jobIndex: result?.data?.jobIndex ?? session.twoWayInfo?.jobIndex,
          threadIndex: result?.data?.threadIndex ?? session.twoWayInfo?.threadIndex,
          jti: result?.data?.jti ?? session.twoWayInfo?.jti,
          twoWayTimestamp: result?.data?.twoWayTimestamp ?? session.twoWayInfo?.twoWayTimestamp,
        },
        step: "email_auth",
      })
      return NextResponse.json({ status: "need_email_auth", sessionId })
    }

    if (code === "CF-00000") {
      await saveSession(sessionId, { step: "done" })
      await saveRegisteredUser(session.baseParams.phoneNo as string, session.baseParams.birthDate as string, id, pw)
      return NextResponse.json({ status: "registered", sessionId })
    }

    return NextResponse.json({ status: "invalid", error: result?.result?.message, errorMessage: extraInfo.errorMessage || "", code })
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "서버 오류"
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
