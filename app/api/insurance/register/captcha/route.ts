import { NextRequest, NextResponse } from "next/server"
import { codefPost } from "@/lib/codef-client"
import { getSession, saveSession } from "@/lib/session-store"

export async function POST(req: NextRequest) {
  try {
    const { sessionId, captchaValue } = await req.json()
    const session = await getSession(sessionId)
    if (!session) return NextResponse.json({ error: "세션 만료. 처음부터 다시 시작해주세요." }, { status: 404 })

    const params = {
      ...session.baseParams,
      secureNo: captchaValue,
      secureNoRefresh: "0",
      is2Way: true,
      twoWayInfo: session.twoWayInfo,
    }

    const result = await codefPost("/v1/kr/insurance/0001/credit4u/register", params)
    await saveSession(sessionId, {
      twoWayInfo: {
        jobIndex: result?.data?.jobIndex ?? session.twoWayInfo?.jobIndex,
        threadIndex: result?.data?.threadIndex ?? session.twoWayInfo?.threadIndex,
        jti: result?.data?.jti ?? session.twoWayInfo?.jti,
        twoWayTimestamp: result?.data?.twoWayTimestamp ?? session.twoWayInfo?.twoWayTimestamp,
      },
      step: "sms_or_pass",
    })

    return NextResponse.json({ sessionId, step: "sms_or_pass" })
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "서버 오류"
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
