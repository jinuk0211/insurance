import { sql } from "drizzle-orm"
import { pgTable, uuid, text, integer, timestamp, index, jsonb, uniqueIndex, boolean } from "drizzle-orm/pg-core"

/** 보험 조회 이력 — 전체 결과는 payloadCipher에 암호화 저장, 평문 컬럼은 최소. */
export const insuranceQueryHistory = pgTable(
  "insurance_query_history",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    userKey: text("user_key").notNull(),
    sourceKey: text("source_key"),
    queriedAt: timestamp("queried_at", { withTimezone: true }).defaultNow().notNull(),
    env: text("env").notNull(),
    nameMasked: text("name_masked"),
    contractCount: integer("contract_count").notNull().default(0),
    totalPremium: integer("total_premium").notNull().default(0),
    payloadCipher: text("payload_cipher").notNull(),
  },
  (t) => ({
    userKeyIdx: index("iqh_user_key_idx").on(t.userKey),
    sourceKeyUniqueIdx: uniqueIndex("iqh_source_key_unique_idx")
      .on(t.sourceKey)
      .where(sql`${t.sourceKey} IS NOT NULL`),
  })
)

/** 조회 이력에서 파생한 대시보드용 요약. 원본 암호문과 1:1로 함께 수명주기를 관리한다. */
export const insuranceDashboardSnapshot = pgTable("insurance_dashboard_snapshot", {
  historyId: uuid("history_id")
    .primaryKey()
    .references(() => insuranceQueryHistory.id, { onDelete: "cascade" }),
  activeCount: integer("active_count").notNull().default(0),
  inactiveCount: integer("inactive_count").notNull().default(0),
  totalPremium: integer("total_premium").notNull().default(0),
  categoryCounts: jsonb("category_counts").$type<Record<string, number>>().notNull(),
  generatedAt: timestamp("generated_at", { withTimezone: true }).defaultNow().notNull(),
})

/** CODEF 멀티스텝 인증 세션 — 서버리스 다중 인스턴스 대응(메모리 Map 대체). 전체 암호화. */
export const codefSession = pgTable("codef_session", {
  id: text("id").primaryKey(),
  dataCipher: text("data_cipher").notNull(),
  expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
})

/** 등록 완료 사용자 — 같은 정보 재입력 시 재인증 없이 바로 조회. 자격증명은 암호화 저장. */
export const registeredUser = pgTable("registered_user", {
  userKey: text("user_key").primaryKey(),
  credCipher: text("cred_cipher").notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
})

/** 서버에서 CODEF 호출 총량을 원자적으로 제한하고 실제 시도를 감사하기 위한 로그. */
export const codefApiUsage = pgTable(
  "codef_api_usage",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    env: text("env").notNull(),
    endpoint: text("endpoint").notNull(),
    status: text("status").notNull().default("reserved"),
    requestedAt: timestamp("requested_at", { withTimezone: true }).defaultNow().notNull(),
    completedAt: timestamp("completed_at", { withTimezone: true }),
  },
  (t) => ({
    envRequestedAtIdx: index("cau_env_requested_at_idx").on(t.env, t.requestedAt),
  }),
)

/** 의료·연금 CODEF 결과의 최소 정규화본. PHI이므로 payload는 항상 AES-256-GCM 암호화한다. */
export const codefDatasetSnapshot = pgTable(
  "codef_dataset_snapshot",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    userKey: text("user_key").notNull(),
    datasetKey: text("dataset_key").notNull(),
    env: text("env").notNull(),
    payloadCipher: text("payload_cipher").notNull(),
    queriedAt: timestamp("queried_at", { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    subjectDatasetUniqueIdx: uniqueIndex("cds_subject_dataset_env_unique")
      .on(t.userKey, t.datasetKey, t.env),
    subjectUpdatedIdx: index("cds_subject_updated_idx").on(t.userKey, t.updatedAt),
  }),
)

/** PHI 접근 감사기록. 원문·이름·전화번호는 기록하지 않고 불투명 userKey만 저장한다. */
export const phiAccessAudit = pgTable(
  "phi_access_audit",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    userKey: text("user_key").notNull(),
    datasetKey: text("dataset_key").notNull(),
    action: text("action").notNull(),
    resourceId: uuid("resource_id"),
    occurredAt: timestamp("occurred_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    subjectOccurredIdx: index("paa_subject_occurred_idx").on(t.userKey, t.occurredAt),
  }),
)

/** 보험사 공시 수집원. adapter별 커서로 전체 목록을 작은 배치로 순회한다. */
export const catalogSource = pgTable("catalog_source", {
  id: text("id").primaryKey(),
  insurerName: text("insurer_name").notNull(),
  adapter: text("adapter").notNull(),
  baseUrl: text("base_url").notNull(),
  category: text("category"),
  active: boolean("active").notNull().default(true),
  cursor: jsonb("cursor").$type<Record<string, unknown>>(),
  lastSuccessAt: timestamp("last_success_at", { withTimezone: true }),
  lastErrorAt: timestamp("last_error_at", { withTimezone: true }),
  lastError: text("last_error"),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
})

/** 공시 수집 실행 이력. 원문이나 고객정보 없이 건수와 오류만 기록한다. */
export const catalogCollectionRun = pgTable(
  "catalog_collection_run",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    sourceId: text("source_id").notNull().references(() => catalogSource.id),
    status: text("status").notNull().default("running"),
    cursorBefore: jsonb("cursor_before").$type<Record<string, unknown>>(),
    cursorAfter: jsonb("cursor_after").$type<Record<string, unknown>>(),
    productsSeen: integer("products_seen").notNull().default(0),
    versionsSeen: integer("versions_seen").notNull().default(0),
    documentsSeen: integer("documents_seen").notNull().default(0),
    revisionsCreated: integer("revisions_created").notNull().default(0),
    reviewItemsCreated: integer("review_items_created").notNull().default(0),
    errorMessage: text("error_message"),
    startedAt: timestamp("started_at", { withTimezone: true }).defaultNow().notNull(),
    finishedAt: timestamp("finished_at", { withTimezone: true }),
  },
  (t) => ({
    sourceStartedIdx: index("ccr_source_started_idx").on(t.sourceId, t.startedAt),
  }),
)

/** 보험사 상품코드 기준 상품 마스터. */
export const insuranceProductMaster = pgTable(
  "insurance_product_master",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    sourceId: text("source_id").notNull().references(() => catalogSource.id),
    insurerName: text("insurer_name").notNull(),
    externalProductCode: text("external_product_code").notNull(),
    canonicalName: text("canonical_name").notNull(),
    productType: text("product_type"),
    saleStatus: text("sale_status").notNull().default("unknown"),
    firstSeenAt: timestamp("first_seen_at", { withTimezone: true }).defaultNow().notNull(),
    lastSeenAt: timestamp("last_seen_at", { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    sourceCodeUniqueIdx: uniqueIndex("ipm_source_code_unique").on(t.sourceId, t.externalProductCode),
    insurerNameIdx: index("ipm_insurer_name_idx").on(t.insurerName, t.canonicalName),
  }),
)

/** 판매시작일별 상품 버전. 이전 버전을 덮어쓰지 않는다. */
export const insuranceProductVersion = pgTable(
  "insurance_product_version",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    productId: uuid("product_id").notNull().references(() => insuranceProductMaster.id),
    externalVersionKey: text("external_version_key").notNull(),
    effectiveFrom: text("effective_from"),
    effectiveTo: text("effective_to"),
    saleStatus: text("sale_status").notNull().default("unknown"),
    sourceFingerprint: text("source_fingerprint").notNull(),
    firstSeenAt: timestamp("first_seen_at", { withTimezone: true }).defaultNow().notNull(),
    lastSeenAt: timestamp("last_seen_at", { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    productVersionUniqueIdx: uniqueIndex("ipv_product_version_unique").on(t.productId, t.externalVersionKey),
    productEffectiveIdx: index("ipv_product_effective_idx").on(t.productId, t.effectiveFrom),
  }),
)

/** 상품에 포함되는 특약의 원본명 마스터. 공시 문서 파서가 확인한 항목만 적재한다. */
export const insuranceRiderMaster = pgTable(
  "insurance_rider_master",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    productId: uuid("product_id").notNull().references(() => insuranceProductMaster.id),
    externalRiderCode: text("external_rider_code"),
    rawName: text("raw_name").notNull(),
    canonicalName: text("canonical_name"),
    firstSeenAt: timestamp("first_seen_at", { withTimezone: true }).defaultNow().notNull(),
    lastSeenAt: timestamp("last_seen_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    productRawNameUniqueIdx: uniqueIndex("irm_product_raw_name_unique").on(t.productId, t.rawName),
  }),
)

/** 특약도 상품과 독립적으로 시행기간별 버전을 보존한다. */
export const insuranceRiderVersion = pgTable(
  "insurance_rider_version",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    riderId: uuid("rider_id").notNull().references(() => insuranceRiderMaster.id),
    externalVersionKey: text("external_version_key").notNull(),
    effectiveFrom: text("effective_from"),
    effectiveTo: text("effective_to"),
    coverageRules: jsonb("coverage_rules").$type<Record<string, unknown>>(),
    reviewStatus: text("review_status").notNull().default("needs_review"),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    riderVersionUniqueIdx: uniqueIndex("irv_rider_version_unique").on(t.riderId, t.externalVersionKey),
  }),
)

/** 상품 버전에 연결된 약관·사업방법서·상품요약서의 논리 문서. */
export const policyDocument = pgTable(
  "policy_document",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    sourceId: text("source_id").notNull().references(() => catalogSource.id),
    productVersionId: uuid("product_version_id").notNull().references(() => insuranceProductVersion.id),
    documentKind: text("document_kind").notNull(),
    sourceUrl: text("source_url").notNull(),
    sourceFileName: text("source_file_name"),
    snapshotStatus: text("snapshot_status").notNull().default("remote_only"),
    parseStatus: text("parse_status").notNull().default("pending"),
    firstSeenAt: timestamp("first_seen_at", { withTimezone: true }).defaultNow().notNull(),
    lastSeenAt: timestamp("last_seen_at", { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    versionKindUrlUniqueIdx: uniqueIndex("pd_version_kind_url_unique").on(t.productVersionId, t.documentKind, t.sourceUrl),
    parseStatusIdx: index("pd_parse_status_idx").on(t.parseStatus, t.lastSeenAt),
  }),
)

/** 문서 원본의 불변 스냅샷. 동일 URL의 파일이 바뀌면 새 revision을 만든다. */
export const policyDocumentRevision = pgTable(
  "policy_document_revision",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    documentId: uuid("document_id").notNull().references(() => policyDocument.id),
    contentHash: text("content_hash").notNull(),
    contentType: text("content_type"),
    byteLength: integer("byte_length"),
    capturedAt: timestamp("captured_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    documentHashUniqueIdx: uniqueIndex("pdr_document_hash_unique").on(t.documentId, t.contentHash),
    capturedIdx: index("pdr_captured_idx").on(t.capturedAt),
  }),
)

/** 문서 revision에서 추출된 조항과 원문 페이지. */
export const policyClause = pgTable(
  "policy_clause",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    revisionId: uuid("revision_id").notNull().references(() => policyDocumentRevision.id),
    clauseType: text("clause_type").notNull(),
    sourcePage: integer("source_page").notNull(),
    excerpt: text("excerpt").notNull(),
    structuredData: jsonb("structured_data").$type<Record<string, unknown>>(),
    confidence: integer("confidence"),
    reviewStatus: text("review_status").notNull().default("needs_review"),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    revisionClausePageUniqueIdx: uniqueIndex("pc_revision_clause_page_unique").on(t.revisionId, t.clauseType, t.sourcePage),
  }),
)

/** 날짜·상품코드·특약 연결이 불명확할 때 자동 적용하지 않고 사람에게 보내는 큐. */
export const catalogReviewQueue = pgTable(
  "catalog_review_queue",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    dedupeKey: text("dedupe_key").notNull(),
    entityType: text("entity_type").notNull(),
    entityId: text("entity_id").notNull(),
    reasonCode: text("reason_code").notNull(),
    status: text("status").notNull().default("open"),
    details: jsonb("details").$type<Record<string, unknown>>(),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
    resolvedAt: timestamp("resolved_at", { withTimezone: true }),
  },
  (t) => ({
    dedupeUniqueIdx: uniqueIndex("crq_dedupe_unique").on(t.dedupeKey),
    statusCreatedIdx: index("crq_status_created_idx").on(t.status, t.createdAt),
  }),
)
