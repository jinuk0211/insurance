import { randomUUID } from "node:crypto"
import { NextRequest, NextResponse } from "next/server"
import { z } from "zod"
import { codefPost } from "@/lib/codef-client"
import {
  CODEF_DATASETS,
  isCodefDatasetKey,
  type CodefDatasetKey,
} from "@/lib/codef-dataset-definitions"
import { buildCodefDatasetParams } from "@/lib/codef-dataset-params"
import { normalizeCodefDataset, type CodefDatasetResult } from "@/lib/codef-dataset-normalizer"
import { getDatasetSnapshot, saveDatasetSnapshot } from "@/lib/db/dataset-snapshot"
import { deriveUserKey } from "@/lib/user-key"
import { deleteSession, saveSession } from "@/lib/session-store"
import {
  createSubjectAccessToken,
  SUBJECT_ACCESS_COOKIE,
  SUBJECT_ACCESS_COOKIE_OPTIONS,
  verifySubjectAccessToken,
} from "@/lib/subject-access"

const DatasetStartInput = z.object({
  datasetKey: z.string().refine(isCodefDatasetKey, "지원하지 않는 조회 항목입니다."),
  userName: z.string().trim().min(2).max(30),
  birthDate: z.string().regex(/^\d{8}$/),
  phoneNo: z.string().transform((value) => value.replace(/\D/g, "")).pipe(z.string().regex(/^01\d{8,9}$/)),
  telecom: z.enum(["0", "1", "2", "3", "4", "5"]),
  startDate: z.string().regex(/^\d{8}$/).optional(),
  endDate: z.string().regex(/^\d{8}$/).optional(),
  consent: z.literal(true),
  refresh: z.boolean().optional().default(false),
}).superRefine((value, context) => {
  if (!isCodefDatasetKey(value.datasetKey)) return
  const definition = CODEF_DATASETS[value.datasetKey]
  if (definition.requiresPeriod && (!value.startDate || !value.endDate)) {
    context.addIssue({ code: z.ZodIssueCode.custom, message: "조회 시작일과 종료일이 필요합니다." })
  }
  if (value.startDate && value.endDate && value.startDate > value.endDate) {
    context.addIssue({ code: z.ZodIssueCode.custom, message: "조회기간을 다시 확인해 주세요." })
  }
})

function datasetSuccess(
  data: CodefDatasetResult,
  userKey: string,
  metadata: { cached: boolean; cachedAt?: string },
) {
  const response = NextResponse.json({ status: "success", data, ...metadata })
  response.cookies.set(
    SUBJECT_ACCESS_COOKIE,
    createSubjectAccessToken(userKey),
    SUBJECT_ACCESS_COOKIE_OPTIONS,
  )
  return response
}
function codefErrorMessage(code: unknown): string {
  if (code === "CF-12801" || code === "CF-12802") return "인증정보를 다시 확인해 주세요."
  if (code === "CF-03004") return "본인인증 시간이 만료되었습니다. 다시 요청해 주세요."
  return "기관 조회를 완료하지 못했습니다. 잠시 후 다시 시도해 주세요."
}

export async function POST(req: NextRequest) {
  let sessionId: string | null = null
  try {
    const parsed = DatasetStartInput.safeParse(await req.json())
    if (!parsed.success) {
      return NextResponse.json({ status: "error", error: "조회 정보와 동의 항목을 다시 확인해 주세요." }, { status: 400 })
    }

    const input = parsed.data
    const datasetKey = input.datasetKey as CodefDatasetKey
    const userKey = deriveUserKey(input.phoneNo, input.birthDate)
    const accessToken = req.cookies.get(SUBJECT_ACCESS_COOKIE)?.value
    const canReadCache = verifySubjectAccessToken(accessToken, userKey)

    if (!input.refresh && canReadCache) {
      const cached = await getDatasetSnapshot(userKey, datasetKey)
      if (cached) return datasetSuccess(cached.data, userKey, { cached: true, cachedAt: cached.queriedAt })
    }

    sessionId = randomUUID()
    const params = buildCodefDatasetParams({ ...input, datasetKey })
    await saveSession(sessionId, {
      baseParams: {
        userName: input.userName,
        birthDate: input.birthDate,
        phoneNo: input.phoneNo,
      },
      queryParams: params,
      datasetKey,
      datasetUserKey: userKey,
      step: "dataset_auth",
    })

    const result = await codefPost(CODEF_DATASETS[datasetKey].endpoint, params)
    const code = result?.result?.code

    if (code === "CF-03002" || code === "CF-03003") {
      await saveSession(sessionId, {
        queryTwoWayInfo: {
          jobIndex: result?.data?.jobIndex ?? 0,
          threadIndex: result?.data?.threadIndex ?? 0,
          jti: result?.data?.jti ?? "",
          twoWayTimestamp: result?.data?.twoWayTimestamp ?? Date.now(),
        },
      })
      return NextResponse.json({
        status: "need_auth",
        sessionId,
        message: "휴대폰의 인증 요청을 승인한 뒤 인증 완료를 눌러 주세요.",
      })
    }

    if (code === "CF-00000") {
      const normalized = normalizeCodefDataset(datasetKey, result?.data)
      await saveDatasetSnapshot(userKey, datasetKey, normalized)
      await deleteSession(sessionId)
      return datasetSuccess(normalized, userKey, { cached: false })
    }

    await deleteSession(sessionId)
    return NextResponse.json({ status: "error", error: codefErrorMessage(code), code }, { status: 400 })
  } catch {
    if (sessionId) {
      try { await deleteSession(sessionId) } catch { /* no PHI in logs */ }
    }
    return NextResponse.json({ status: "error", error: "안전한 조회 처리 중 오류가 발생했습니다." }, { status: 500 })
  }
}
