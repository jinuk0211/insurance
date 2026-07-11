CREATE TABLE "codef_session" (
	"id" text PRIMARY KEY NOT NULL,
	"data_cipher" text NOT NULL,
	"expires_at" timestamp with time zone NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "insurance_dashboard_snapshot" (
	"history_id" uuid PRIMARY KEY NOT NULL,
	"active_count" integer DEFAULT 0 NOT NULL,
	"inactive_count" integer DEFAULT 0 NOT NULL,
	"total_premium" integer DEFAULT 0 NOT NULL,
	"category_counts" jsonb NOT NULL,
	"generated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "insurance_query_history" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_key" text NOT NULL,
	"source_key" text,
	"queried_at" timestamp with time zone DEFAULT now() NOT NULL,
	"env" text NOT NULL,
	"name_masked" text,
	"contract_count" integer DEFAULT 0 NOT NULL,
	"total_premium" integer DEFAULT 0 NOT NULL,
	"payload_cipher" text NOT NULL
);
--> statement-breakpoint
CREATE TABLE "registered_user" (
	"user_key" text PRIMARY KEY NOT NULL,
	"cred_cipher" text NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "insurance_dashboard_snapshot" ADD CONSTRAINT "insurance_dashboard_snapshot_history_id_insurance_query_history_id_fk" FOREIGN KEY ("history_id") REFERENCES "public"."insurance_query_history"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "iqh_user_key_idx" ON "insurance_query_history" USING btree ("user_key");--> statement-breakpoint
CREATE UNIQUE INDEX "iqh_source_key_unique_idx" ON "insurance_query_history" USING btree ("source_key") WHERE "insurance_query_history"."source_key" IS NOT NULL;