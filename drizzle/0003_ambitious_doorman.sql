CREATE TABLE "catalog_collection_run" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"source_id" text NOT NULL,
	"status" text DEFAULT 'running' NOT NULL,
	"cursor_before" jsonb,
	"cursor_after" jsonb,
	"products_seen" integer DEFAULT 0 NOT NULL,
	"versions_seen" integer DEFAULT 0 NOT NULL,
	"documents_seen" integer DEFAULT 0 NOT NULL,
	"revisions_created" integer DEFAULT 0 NOT NULL,
	"review_items_created" integer DEFAULT 0 NOT NULL,
	"error_message" text,
	"started_at" timestamp with time zone DEFAULT now() NOT NULL,
	"finished_at" timestamp with time zone
);
--> statement-breakpoint
CREATE TABLE "catalog_review_queue" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"dedupe_key" text NOT NULL,
	"entity_type" text NOT NULL,
	"entity_id" text NOT NULL,
	"reason_code" text NOT NULL,
	"status" text DEFAULT 'open' NOT NULL,
	"details" jsonb,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"resolved_at" timestamp with time zone
);
--> statement-breakpoint
CREATE TABLE "catalog_source" (
	"id" text PRIMARY KEY NOT NULL,
	"insurer_name" text NOT NULL,
	"adapter" text NOT NULL,
	"base_url" text NOT NULL,
	"category" text,
	"active" boolean DEFAULT true NOT NULL,
	"cursor" jsonb,
	"last_success_at" timestamp with time zone,
	"last_error_at" timestamp with time zone,
	"last_error" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "insurance_product_master" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"source_id" text NOT NULL,
	"insurer_name" text NOT NULL,
	"external_product_code" text NOT NULL,
	"canonical_name" text NOT NULL,
	"product_type" text,
	"sale_status" text DEFAULT 'unknown' NOT NULL,
	"first_seen_at" timestamp with time zone DEFAULT now() NOT NULL,
	"last_seen_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "insurance_product_version" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"product_id" uuid NOT NULL,
	"external_version_key" text NOT NULL,
	"effective_from" text,
	"effective_to" text,
	"sale_status" text DEFAULT 'unknown' NOT NULL,
	"source_fingerprint" text NOT NULL,
	"first_seen_at" timestamp with time zone DEFAULT now() NOT NULL,
	"last_seen_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "insurance_rider_master" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"product_id" uuid NOT NULL,
	"external_rider_code" text,
	"raw_name" text NOT NULL,
	"canonical_name" text,
	"first_seen_at" timestamp with time zone DEFAULT now() NOT NULL,
	"last_seen_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "insurance_rider_version" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"rider_id" uuid NOT NULL,
	"external_version_key" text NOT NULL,
	"effective_from" text,
	"effective_to" text,
	"coverage_rules" jsonb,
	"review_status" text DEFAULT 'needs_review' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "policy_clause" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"revision_id" uuid NOT NULL,
	"clause_type" text NOT NULL,
	"source_page" integer NOT NULL,
	"excerpt" text NOT NULL,
	"structured_data" jsonb,
	"confidence" integer,
	"review_status" text DEFAULT 'needs_review' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "policy_document" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"source_id" text NOT NULL,
	"product_version_id" uuid NOT NULL,
	"document_kind" text NOT NULL,
	"source_url" text NOT NULL,
	"source_file_name" text,
	"snapshot_status" text DEFAULT 'remote_only' NOT NULL,
	"parse_status" text DEFAULT 'pending' NOT NULL,
	"first_seen_at" timestamp with time zone DEFAULT now() NOT NULL,
	"last_seen_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "policy_document_revision" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"document_id" uuid NOT NULL,
	"content_hash" text NOT NULL,
	"content_type" text,
	"byte_length" integer,
	"captured_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "catalog_collection_run" ADD CONSTRAINT "catalog_collection_run_source_id_catalog_source_id_fk" FOREIGN KEY ("source_id") REFERENCES "public"."catalog_source"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "insurance_product_master" ADD CONSTRAINT "insurance_product_master_source_id_catalog_source_id_fk" FOREIGN KEY ("source_id") REFERENCES "public"."catalog_source"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "insurance_product_version" ADD CONSTRAINT "insurance_product_version_product_id_insurance_product_master_id_fk" FOREIGN KEY ("product_id") REFERENCES "public"."insurance_product_master"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "insurance_rider_master" ADD CONSTRAINT "insurance_rider_master_product_id_insurance_product_master_id_fk" FOREIGN KEY ("product_id") REFERENCES "public"."insurance_product_master"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "insurance_rider_version" ADD CONSTRAINT "insurance_rider_version_rider_id_insurance_rider_master_id_fk" FOREIGN KEY ("rider_id") REFERENCES "public"."insurance_rider_master"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "policy_clause" ADD CONSTRAINT "policy_clause_revision_id_policy_document_revision_id_fk" FOREIGN KEY ("revision_id") REFERENCES "public"."policy_document_revision"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "policy_document" ADD CONSTRAINT "policy_document_source_id_catalog_source_id_fk" FOREIGN KEY ("source_id") REFERENCES "public"."catalog_source"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "policy_document" ADD CONSTRAINT "policy_document_product_version_id_insurance_product_version_id_fk" FOREIGN KEY ("product_version_id") REFERENCES "public"."insurance_product_version"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "policy_document_revision" ADD CONSTRAINT "policy_document_revision_document_id_policy_document_id_fk" FOREIGN KEY ("document_id") REFERENCES "public"."policy_document"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "ccr_source_started_idx" ON "catalog_collection_run" USING btree ("source_id","started_at");--> statement-breakpoint
CREATE UNIQUE INDEX "crq_dedupe_unique" ON "catalog_review_queue" USING btree ("dedupe_key");--> statement-breakpoint
CREATE INDEX "crq_status_created_idx" ON "catalog_review_queue" USING btree ("status","created_at");--> statement-breakpoint
CREATE UNIQUE INDEX "ipm_source_code_unique" ON "insurance_product_master" USING btree ("source_id","external_product_code");--> statement-breakpoint
CREATE INDEX "ipm_insurer_name_idx" ON "insurance_product_master" USING btree ("insurer_name","canonical_name");--> statement-breakpoint
CREATE UNIQUE INDEX "ipv_product_version_unique" ON "insurance_product_version" USING btree ("product_id","external_version_key");--> statement-breakpoint
CREATE INDEX "ipv_product_effective_idx" ON "insurance_product_version" USING btree ("product_id","effective_from");--> statement-breakpoint
CREATE UNIQUE INDEX "irm_product_raw_name_unique" ON "insurance_rider_master" USING btree ("product_id","raw_name");--> statement-breakpoint
CREATE UNIQUE INDEX "irv_rider_version_unique" ON "insurance_rider_version" USING btree ("rider_id","external_version_key");--> statement-breakpoint
CREATE UNIQUE INDEX "pc_revision_clause_page_unique" ON "policy_clause" USING btree ("revision_id","clause_type","source_page");--> statement-breakpoint
CREATE UNIQUE INDEX "pd_version_kind_url_unique" ON "policy_document" USING btree ("product_version_id","document_kind","source_url");--> statement-breakpoint
CREATE INDEX "pd_parse_status_idx" ON "policy_document" USING btree ("parse_status","last_seen_at");--> statement-breakpoint
CREATE UNIQUE INDEX "pdr_document_hash_unique" ON "policy_document_revision" USING btree ("document_id","content_hash");--> statement-breakpoint
CREATE INDEX "pdr_captured_idx" ON "policy_document_revision" USING btree ("captured_at");