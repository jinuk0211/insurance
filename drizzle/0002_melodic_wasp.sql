CREATE TABLE "codef_dataset_snapshot" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_key" text NOT NULL,
	"dataset_key" text NOT NULL,
	"env" text NOT NULL,
	"payload_cipher" text NOT NULL,
	"queried_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "phi_access_audit" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_key" text NOT NULL,
	"dataset_key" text NOT NULL,
	"action" text NOT NULL,
	"resource_id" uuid,
	"occurred_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX "cds_subject_dataset_env_unique" ON "codef_dataset_snapshot" USING btree ("user_key","dataset_key","env");--> statement-breakpoint
CREATE INDEX "cds_subject_updated_idx" ON "codef_dataset_snapshot" USING btree ("user_key","updated_at");--> statement-breakpoint
CREATE INDEX "paa_subject_occurred_idx" ON "phi_access_audit" USING btree ("user_key","occurred_at");