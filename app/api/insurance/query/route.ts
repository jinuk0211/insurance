import { NextRequest, NextResponse } from "next/server"
import { codefPost, rsaEncrypt } from "@/lib/codef-client"
import { getSession, saveSession } from "@/lib/session-store"
import { getRecentQueryResult, saveQueryHistory } from "@/lib/db/history"
import { saveRegisteredUser } from "@/lib/db/registered-user"
import { z } from "zod"

const QueryInput = z.object({ sessionId: z.string().uuid() })

export async function POST(req: NextRequest) {
  try {
    const parsed = QueryInput.safeParse(await req.json())
    if (!parsed.success) {
      return NextResponse.json({ status: "error", error: "조회 요청 정보를 다시 확인해주세요." }, { status: 400 })
    }
    const { sessionId } = parsed.data
    const session = await getSession(sessionId)
    if (!session) return NextResponse.json({ status: "error", error: "인증이 만료됐습니다. 처음부터 다시 시도해주세요." }, { status: 400 })

    const cached = await getRecentQueryResult(session.baseParams)
    if (cached) {
      return NextResponse.json({
        status: "success",
        data: cached.data,
        cached: true,
        cachedAt: cached.queriedAt,
      })
    }

    const params = {
      organization: "0001",
      id: session.loginId || session.finalId || session.regId || "",
      password: rsaEncrypt(session.loginPw || session.finalPw || session.regPw || ""),
      type: "0",
      userName: session.baseParams.userName,
      birthDate: session.baseParams.birthDate,
      phoneNo: session.baseParams.phoneNo,
      telecom: session.baseParams.telecom,
      authMethod: session.baseParams.authMethod,
      timeOut: "170",
    }

    const result = await codefPost("/v1/kr/insurance/0001/credit4u/contract-info", params)
    const code = result?.result?.code

    // Handle password lock error
    if (code === "CF-12802") {
      return NextResponse.json({
        status: "error",
        error: "비밀번호 오류 횟수가 초과되었습니다. 내보험다보여 사이트에서 비밀번호를 재설정 후 다시 시도해주세요."
      }, { status: 400 })
    }

    if (code === "CF-03002") {
      const extraInfo = result?.data?.extraInfo || {}
      await saveSession(sessionId, {
        queryTwoWayInfo: {
          jobIndex: result?.data?.jobIndex ?? 0,
          threadIndex: result?.data?.threadIndex ?? 0,
          jti: result?.data?.jti ?? "",
          twoWayTimestamp: result?.data?.twoWayTimestamp ?? Date.now(),
        },
        queryParams: params,
      })
      return NextResponse.json({ status: "need_auth", sessionId, authMethod: session.baseParams.authMethod, extraInfo })
    }

    if (code === "CF-00000") {
      // 조회가 성공했다 = 자격증명이 동작한다. 다음부턴 재인증 없이 인식되도록 저장.
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
      // 이력 저장은 부가 기능 — 실패해도 사용자 조회 응답은 막지 않는다.
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
