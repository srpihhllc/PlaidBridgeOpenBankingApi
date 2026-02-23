import { z } from "zod";
import { router, publicProcedure, protectedProcedure } from "../trpc";
import { db } from "../db";
import { alerts } from "@/drizzle/schema";
import { eq, and, desc, isNull } from "drizzle-orm";

export const alertsRouter = router({
  /**
   * Get all active alerts for the current user
   */
  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().int().positive().default(10),
        offset: z.number().int().nonnegative().default(0),
        includeDismissed: z.boolean().default(false),
      })
    )
    .query(async ({ ctx, input }: any) => {
      const whereCondition = input.includeDismissed
        ? eq(alerts.userId, ctx.user.id)
        : and(
            eq(alerts.userId, ctx.user.id),
            eq(alerts.isDismissed, false)
          );

      const userAlerts = await db
        .select()
        .from(alerts)
        .where(whereCondition)
        .orderBy(desc(alerts.createdAt))
        .limit(input.limit)
        .offset(input.offset);

      return userAlerts;
    }),

  /**
   * Get a single alert by ID
   */
  get: protectedProcedure
    .input(z.object({ id: z.number().int().positive() }))
    .query(async ({ ctx, input }: any) => {
      const alert = await db
        .select()
        .from(alerts)
        .where(and(eq(alerts.id, input.id), eq(alerts.userId, ctx.user.id)))
        .then((result) => result[0]);

      return alert || null;
    }),

  /**
   * Create a new alert (admin/system only)
   */
  create: protectedProcedure
    .input(
      z.object({
        accountId: z.number().int().positive().optional(),
        title: z.string().min(1).max(255),
        message: z.string().min(1),
        type: z.enum(["warning", "info", "success", "error"]).default("info"),
        severity: z
          .enum(["low", "medium", "high", "critical"])
          .default("medium"),
        actionUrl: z.string().url().optional(),
      })
    )
    .mutation(async ({ ctx, input }: any) => {
      const newAlert = await db
        .insert(alerts)
        .values({
          userId: ctx.user.id,
          accountId: input.accountId,
          title: input.title,
          message: input.message,
          type: input.type,
          severity: input.severity,
          actionUrl: input.actionUrl,
        })
        .then((result: any) => {
          return {
            id: result.insertId,
            userId: ctx.user.id,
            accountId: input.accountId,
            title: input.title,
            message: input.message,
            type: input.type,
            severity: input.severity,
            isDismissed: false,
            dismissedAt: null,
            actionUrl: input.actionUrl || null,
            createdAt: new Date(),
            updatedAt: new Date(),
          };
        });

      return newAlert;
    }),

  /**
   * Dismiss an alert
   */
  dismiss: protectedProcedure
    .input(z.object({ id: z.number().int().positive() }))
    .mutation(async ({ ctx, input }: any) => {
      const result = await db
        .update(alerts)
        .set({
          isDismissed: true,
          dismissedAt: new Date(),
          updatedAt: new Date(),
        })
        .where(and(eq(alerts.id, input.id), eq(alerts.userId, ctx.user.id)));

      return { success: true };
    }),

  /**
   * Dismiss all alerts for the current user
   */
  dismissAll: protectedProcedure.mutation(async ({ ctx }: any) => {
    await db
      .update(alerts)
      .set({
        isDismissed: true,
        dismissedAt: new Date(),
        updatedAt: new Date(),
      })
      .where(
        and(eq(alerts.userId, ctx.user.id), eq(alerts.isDismissed, false))
      );

    return { success: true };
  }),

  /**
   * Get count of unread alerts
   */
  unreadCount: protectedProcedure.query(async ({ ctx }: any) => {
    const result = await db
      .select()
      .from(alerts)
      .where(
        and(eq(alerts.userId, ctx.user.id), eq(alerts.isDismissed, false))
      );

    return { count: result.length };
  }),
});
