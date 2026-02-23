import { z } from "zod";
import { COOKIE_NAME } from "../shared/const.js";
import { getSessionCookieOptions } from "./_core/cookies";
import { systemRouter } from "./_core/systemRouter";
import { publicProcedure, router, protectedProcedure } from "./_core/trpc";
import * as db from "./db";

export const appRouter = router({
  system: systemRouter,
  
  auth: router({
    me: publicProcedure.query((opts) => opts.ctx.user),
    logout: publicProcedure.mutation(({ ctx }) => {
      const cookieOptions = getSessionCookieOptions(ctx.req);
      ctx.res.clearCookie(COOKIE_NAME, { ...cookieOptions, maxAge: -1 });
      return { success: true } as const;
    }),
  }),

  accounts: router({
    list: protectedProcedure.query(({ ctx }) => 
      db.getUserAccounts(ctx.user.id)
    ),
    
    get: protectedProcedure
      .input(z.object({ id: z.number() }))
      .query(({ ctx, input }) => 
        db.getAccountById(input.id, ctx.user.id)
      ),
    
    create: protectedProcedure
      .input(z.object({
        accountNumber: z.string().min(1).max(20),
        accountType: z.enum(["checking", "savings", "investment"]),
        accountName: z.string().min(1).max(255),
        currency: z.string().length(3).default("USD"),
      }))
      .mutation(({ ctx, input }) => 
        db.createAccount({ userId: ctx.user.id, ...input })
      ),
    
    update: protectedProcedure
      .input(z.object({
        id: z.number(),
        accountName: z.string().max(255).optional(),
        status: z.enum(["active", "frozen", "closed"]).optional(),
      }))
      .mutation(({ ctx, input }) => 
        db.updateAccount(input.id, ctx.user.id, input)
      ),
  }),

  cards: router({
    list: protectedProcedure.query(({ ctx }) => 
      db.getUserCards(ctx.user.id)
    ),
    
    get: protectedProcedure
      .input(z.object({ id: z.number() }))
      .query(({ ctx, input }) => 
        db.getCardById(input.id, ctx.user.id)
      ),
    
    create: protectedProcedure
      .input(z.object({
        accountId: z.number(),
        cardNumber: z.string().min(13).max(20),
        cardType: z.enum(["debit", "credit"]),
        cardBrand: z.string().min(1).max(50),
        holderName: z.string().min(1).max(255),
        expiryDate: z.string(),
        cvv: z.string(),
      }))
      .mutation(({ ctx, input }) => 
        db.createCard({ userId: ctx.user.id, ...input })
      ),
    
    update: protectedProcedure
      .input(z.object({
        id: z.number(),
        status: z.enum(["active", "blocked", "expired"]).optional(),
      }))
      .mutation(({ ctx, input }) => 
        db.updateCard(input.id, ctx.user.id, input)
      ),
  }),

  transactions: router({
    list: protectedProcedure
      .input(z.object({
        limit: z.number().default(50),
        offset: z.number().default(0),
      }))
      .query(({ ctx, input }) => 
        db.getUserTransactions(ctx.user.id, input.limit, input.offset)
      ),
    
    byAccount: protectedProcedure
      .input(z.object({
        accountId: z.number(),
        limit: z.number().default(50),
        offset: z.number().default(0),
      }))
      .query(({ ctx, input }) => 
        db.getAccountTransactions(input.accountId, ctx.user.id, input.limit, input.offset)
      ),
    
    get: protectedProcedure
      .input(z.object({ id: z.number() }))
      .query(({ ctx, input }) => 
        db.getTransactionById(input.id, ctx.user.id)
      ),
    
    create: protectedProcedure
      .input(z.object({
        accountId: z.number(),
        cardId: z.number().optional(),
        transactionType: z.enum(["transfer", "deposit", "withdrawal", "payment", "recharge"]),
        amount: z.string(),
        recipientName: z.string().optional(),
        recipientAccount: z.string().optional(),
        description: z.string().optional(),
      }))
      .mutation(({ ctx, input }) => 
        db.createTransaction({
          userId: ctx.user.id,
          status: "pending",
          ...input,
        })
      ),
    
    update: protectedProcedure
      .input(z.object({
        id: z.number(),
        status: z.enum(["pending", "completed", "failed", "cancelled"]).optional(),
      }))
      .mutation(({ ctx, input }) => 
        db.updateTransaction(input.id, ctx.user.id, input)
      ),
  }),

  beneficiaries: router({
    list: protectedProcedure.query(({ ctx }) => 
      db.getUserBeneficiaries(ctx.user.id)
    ),
    
    get: protectedProcedure
      .input(z.object({ id: z.number() }))
      .query(({ ctx, input }) => 
        db.getBeneficiaryById(input.id, ctx.user.id)
      ),
    
    create: protectedProcedure
      .input(z.object({
        beneficiaryName: z.string().min(1).max(255),
        accountNumber: z.string().min(1).max(20),
        bankName: z.string().min(1).max(255),
      }))
      .mutation(({ ctx, input }) => 
        db.createBeneficiary({ userId: ctx.user.id, ...input })
      ),
    
    update: protectedProcedure
      .input(z.object({
        id: z.number(),
        isFrequent: z.boolean().optional(),
      }))
      .mutation(({ ctx, input }) => 
        db.updateBeneficiary(input.id, ctx.user.id, input)
      ),
    
    delete: protectedProcedure
      .input(z.object({ id: z.number() }))
      .mutation(({ ctx, input }) => 
        db.deleteBeneficiary(input.id, ctx.user.id)
      ),
  }),

  preferences: router({
    get: protectedProcedure.query(({ ctx }) => 
      db.getUserPreferences(ctx.user.id)
    ),
    
    update: protectedProcedure
      .input(z.object({
        theme: z.enum(["light", "dark", "auto"]).optional(),
        language: z.string().max(10).optional(),
        notificationsEnabled: z.boolean().optional(),
        biometricEnabled: z.boolean().optional(),
        twoFactorEnabled: z.boolean().optional(),
      }))
      .mutation(({ ctx, input }) => 
        db.updateUserPreferences(ctx.user.id, input)
      ),
  }),
});

export type AppRouter = typeof appRouter;
