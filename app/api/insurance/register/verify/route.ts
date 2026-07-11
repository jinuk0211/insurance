import { NextRequest, NextResponse } from "next/server"
import { codefPost, rsaEncrypt } from "@/lib/codef-client"
import { getSession, saveSession } from "@/lib/session-store"
import { saveRegisteredUser } from "@/lib/db/registered-user"

export async function POST(req: NextRequest) {
  try {
    const { sessionId, smsAuthNo } = await req.json()
    const session = await getSession(sessionId)
    if (!session) return NextResponse.json({ error: "세션 만료." }, { status: 404 })

    // authMethod "1" = PASS (simpleAuth), "0" = SMS (smsAuthNo)
    const isPass = session.baseParams.authMethod === "1"
    const params = {
      ...session.baseParams,
      smsAuthNo: isPass ? "" : (smsAuthNo || ""),
      simpleAuth: isPass ? "1" : "0",
      is2Way: true,
      twoWayInfo: session.twoWayInfo,
    }

    const result = await codefPost("/v1/kr/insurance/0001/credit4u/register", params)
    const code = result?.result?.code
    const extraInfo = result?.data?.extraInfo || {}

    // Already registered
    if (code === "CF-12069") {
      await saveRegisteredUser(session.baseParams.phoneNo as string, session.baseParams.birthDate as string, session.regId!, session.regPw!)
      await saveSession(sessionId, { loginId: session.regId, loginPw: session.regPw, step: "done" })
      return NextResponse.json({ status: "registered", sessionId })
    }

    // Update twoWayInfo
    if (result?.data?.jti) {
      await saveSession(sessionId, {
        twoWayInfo: {
          jobIndex: result.data.jobIndex ?? session.twoWayInfo?.jobIndex,
          threadIndex: result.data.threadIndex ?? session.twoWayInfo?.threadIndex,
          jti: result.data.jti,
          twoWayTimestamp: result.data.twoWayTimestamp ?? session.twoWayInfo?.twoWayTimestamp,
        },
      })
    }

    // Registration info needed — auto-submit from session
    if ("reqUserId" in extraInfo || "reqUserPass" in extraInfo) {
      const updated = (await getSession(sessionId))!
      const infoParams = {
        ...updated.baseParams,
        id: updated.regId,
        password: rsaEncrypt(updated.regPw!),
        email: updated.regEmail || "",
        is2Way: true,
        twoWayInfo: updated.twoWayInfo,
      }
      const infoResult = await codefPost("/v1/kr/insurance/0001/credit4u/register", infoParams)
      const infoCode = infoResult?.result?.code
      const infoExtra = infoResult?.data?.extraInfo || {}

      if ("reqEmailAuthNo" in infoExtra || infoCode === "CF-03002") {
        await saveSession(sessionId, {
          step: "email_auth",
          twoWayInfo: {
            jobIndex: infoResult?.data?.jobIndex ?? updated.twoWayInfo?.jobIndex,
            threadIndex: infoResult?.data?.threadIndex ?? updated.twoWayInfo?.threadIndex,
            jti: infoResult?.data?.jti ?? updated.twoWayInfo?.jti,
            twoWayTimestamp: infoResult?.data?.twoWayTimestamp ?? updated.twoWayInfo?.twoWayTimestamp,
          },
          finalId: updated.regId,
          finalPw: updated.regPw,
          finalEmail: updated.regEmail,
        })
        return NextResponse.json({ status: "need_email_auth", sessionId })
      }
      if (infoCode === "CF-00000") {
        await saveSession(sessionId, { step: "done" })
        if (updated.regId && updated.regPw) {
          await saveRegisteredUser(updated.baseParams.phoneNo as string, updated.baseParams.birthDate as string, updated.regId, updated.regPw)
        }
        return NextResponse.json({ status: "registered", sessionId })
      }
      return NextResponse.json({ status: "error", error: infoResult?.result?.message, code: infoCode }, { status: 400 })
    }

    if (code === "CF-00000") {
      await saveSession(sessionId, { step: "done" })
      if (session.regId && session.regPw) {
        await saveRegisteredUser(session.baseParams.phoneNo as string, session.baseParams.birthDate as string, session.regId, session.regPw)
      }
      return NextResponse.json({ status: "registered", sessionId })
    }
    if (code === "CF-03002") {
      return NextResponse.json({ status: "pending" })
    }
    if (code === "CF-01004" || code === "CF-00025") {
      return NextResponse.json({ status: "timeout", error: "인증이 만료됐습니다. 처음부터 다시 시도해주세요." }, { status: 400 })
    }

    // Error handling for other CODEF errors
    if (code && code !== "CF-00000" && code !== "CF-03002") {
      const errorMsg = result?.result?.message || "인증 처리 중 오류가 발생했습니다."
      return NextResponse.json({ status: "error", error: errorMsg }, { status: 400 })
    }

    // Still waiting
    return NextResponse.json({ status: "pending" })
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "서버 오류"
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
