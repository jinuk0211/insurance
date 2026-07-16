import { NextRequest, NextResponse } from "next/server"
import { z } from "zod"
import { codefPost } from "@/lib/codef-client"
import {
  CODEF_DATASETS,
  isCodefDatasetKey,
  type CodefDatasetKey,
} from "@/lib/codef-dataset-definitions"
import { normalizeCodefDataset } from "@/lib/codef-dataset-normalizer"
import { saveDatasetSnapshot } from "@/lib/db/dataset-snapshot"
import { deleteSession, getSession, saveSession } from "@/lib/session-store"
import {
  createSubjectAccessToken,
  SUBJECT_ACCESS_COOKIE,
  SUBJECT_ACCESS_COOKIE_OPTIONS,
} from "@/lib/subject-access"

const ConfirmInput = z.object({ sessionId: z.string().uuid() })
const MAX_CONFIRM_ATTEMPTS = 3

export async function POST(req: NextRequest) {
  try {
    const parsed = ConfirmInput.safeParse(await req.json())
    if (!parsed.success) {
      return NextResponse.json({ status: "error", error: "인증 세션을 다시 확인해 주세요." }, { status: 400 })
    }
    const session = await getSession(parsed.data.sessionId)
    if (!session || session.step !== "dataset_auth") {
      return NextResponse.json({ status: "error", error: "인증 시간이 만료되었습니다. 다시 조회해 주세요." }, { status: 404 })
    }
    if (!session.datasetKey || !isCodefDatasetKey(session.datasetKey) || !session.datasetUserKey || !session.queryParams) {
      return NextResponse.json({ status: "error", error: "조회 세션이 올바르지 않습니다." }, { status: 400 })
    }
    const completedAttempts = session.datasetConfirmAttempts ?? 0
    if (completedAttempts >= MAX_CONFIRM_ATTEMPTS) {
      await deleteSession(parsed.data.sessionId)
      return NextResponse.json(
        { status: "error", error: "인증 확인 횟수를 초과했습니다. 새로 조회해 주세요." },
        { status: 429 },
      )
    }
    await saveSession(parsed.data.sessionId, { datasetConfirmAttempts: completedAttempts + 1 })

    const datasetKey = session.datasetKey as CodefDatasetKey
    const params = {
      ...session.queryParams,
      simpleAuth: "1",
      is2Way: true,
      twoWayInfo: session.queryTwoWayInfo,
    }
    const result = await codefPost(CODEF_DATASETS[datasetKey].endpoint, params)
    const code = result?.result?.code

    if (code === "CF-03002" || code === "CF-03003") {
      return NextResponse.json({ status: "pending", message: "휴대폰 인증 승인을 기다리고 있습니다." })
    }
    if (code !== "CF-00000") {
      await deleteSession(parsed.data.sessionId)
      return NextResponse.json({ status: "error", error: "본인인증을 완료하지 못했습니다.", code }, { status: 400 })
    }

    const normalized = normalizeCodefDataset(datasetKey, result?.data)
    await saveDatasetSnapshot(session.datasetUserKey, datasetKey, normalized)
    await deleteSession(parsed.data.sessionId)

    const response = NextResponse.json({ status: "success", data: normalized, cached: false })
    response.cookies.set(
      SUBJECT_ACCESS_COOKIE,
      createSubjectAccessToken(session.datasetUserKey),
      SUBJECT_ACCESS_COOKIE_OPTIONS,
    )
    return response
  } catch {
    return NextResponse.json({ status: "error", error: "안전한 인증 처리 중 오류가 발생했습니다." }, { status: 500 })
  }
}
