import { NextRequest, NextResponse } from "next/server"
import { codefPost, rsaEncrypt } from "@/lib/codef-client"
import { saveSession } from "@/lib/session-store"
import { findRegisteredUser } from "@/lib/db/registered-user"
import { randomUUID } from "crypto"

export async function POST(req: NextRequest) {
  try {
    const { userName, birthDate, phoneNo, telecom = "0", authMethod = "pass", idBack7, regId, regPw, regEmail } =
      await req.json()

    if (!userName || !birthDate || !phoneNo) {
      return NextResponse.json({ error: "이름, 생년월일, 전화번호를 입력해주세요." }, { status: 400 })
    }
    if (!idBack7 || !/^\d{7}$/.test(idBack7)) {
      return NextResponse.json({ error: "주민등록번호 뒤 7자리를 입력해주세요." }, { status: 400 })
    }

    const clean = phoneNo.replace(/-/g, "")

    // Check existing user
    const existing = await findRegisteredUser(clean, birthDate)
    if (existing) {
      const sessionId = randomUUID()
      await saveSession(sessionId, {
        baseParams: { organization: "0001", userName, identity: rsaEncrypt(idBack7), birthDate, identityEncYn: "Y", telecom, phoneNo: clean, timeout: "170", authMethod: authMethod === "pass" ? "1" : "0", type: "1", checkParamUUID: sessionId.replace(/-/g, "").slice(0, 20) },
        regId: existing.id, regPw: existing.pw, regEmail: "", loginId: existing.id, loginPw: existing.pw,
        step: "done",
      })
      return NextResponse.json({ sessionId, step: "already_registered" })
    }

    const sessionId = randomUUID()
    const baseParams = {
      organization: "0001",
      userName,
      identity: rsaEncrypt(idBack7),
      birthDate,
      identityEncYn: "Y",
      telecom,
      phoneNo: clean,
      timeout: "170",
      authMethod: authMethod === "pass" ? "1" : "0",
      type: "1",
      checkParamUUID: sessionId.replace(/-/g, "").slice(0, 20),
    }

    await saveSession(sessionId, { baseParams, regId, regPw, regEmail, step: "start" })

    const result = await codefPost("/v1/kr/insurance/0001/credit4u/register", baseParams)
    const extraInfo = result?.data?.extraInfo || {}
    const twoWayInfo = {
      jobIndex: result?.data?.jobIndex ?? 0,
      threadIndex: result?.data?.threadIndex ?? 0,
      jti: result?.data?.jti ?? "",
      twoWayTimestamp: result?.data?.twoWayTimestamp ?? Date.now(),
    }

    const hasCaptcha = extraInfo.reqSecureNo && extraInfo.reqSecureNo.length > 10
    await saveSession(sessionId, { twoWayInfo, step: hasCaptcha ? "captcha" : "sms_or_pass" })

    return NextResponse.json({
      sessionId,
      step: hasCaptcha ? "captcha" : "sms_or_pass",
      captchaImage: hasCaptcha ? extraInfo.reqSecureNo : null,
      authMethod,
    })
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "서버 오류"
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
