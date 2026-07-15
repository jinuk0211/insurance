CREATE TABLE "codef_api_usage" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"env" text NOT NULL,
	"endpoint" text NOT NULL,
	"status" text DEFAULT 'reserved' NOT NULL,
	"requested_at" timestamp with time zone DEFAULT now() NOT NULL,
	"completed_at" timestamp with time zone
);
--> statement-breakpoint
CREATE INDEX "cau_env_requested_at_idx" ON "codef_api_usage" USING btree ("env","requested_at");