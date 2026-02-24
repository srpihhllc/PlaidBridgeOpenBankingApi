import { int, mysqlEnum, mysqlTable, text, timestamp, varchar, decimal, boolean } from "drizzle-orm/mysql-core";

/**
 * Core user table backing auth flow.
 * Extend this file with additional tables as your product grows.
 * Columns use camelCase to match both database fields and generated types.
 */
export const users = mysqlTable("users", {
  /**
   * Surrogate primary key. Auto-incremented numeric value managed by the database.
   * Use this for relations between tables.
   */
  id: int("id").autoincrement().primaryKey(),
  /** Manus OAuth identifier (openId) returned from the OAuth callback. Unique per user. */
  openId: varchar("openId", { length: 64 }).notNull().unique(),
  name: text("name"),
  email: varchar("email", { length: 320 }),
  loginMethod: varchar("loginMethod", { length: 64 }),
  role: mysqlEnum("role", ["user", "admin"]).default("user").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
  lastSignedIn: timestamp("lastSignedIn").defaultNow().notNull(),
});

export type User = typeof users.$inferSelect;
export type InsertUser = typeof users.$inferInsert;

/**
 * Accounts table - stores user bank accounts
 */
export const accounts = mysqlTable("accounts", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  accountNumber: varchar("accountNumber", { length: 20 }).notNull().unique(),
  accountType: mysqlEnum("accountType", ["checking", "savings", "investment"]).notNull(),
  accountName: varchar("accountName", { length: 255 }).notNull(),
  balance: decimal("balance", { precision: 15, scale: 2 }).notNull().default("0"),
  currency: varchar("currency", { length: 3 }).notNull().default("USD"),
  status: mysqlEnum("status", ["active", "frozen", "closed"]).notNull().default("active"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
});

export type Account = typeof accounts.$inferSelect;
export type InsertAccount = typeof accounts.$inferInsert;

/**
 * Cards table - stores user payment cards
 */
export const cards = mysqlTable("cards", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  accountId: int("accountId").notNull(),
  cardNumber: varchar("cardNumber", { length: 20 }).notNull().unique(),
  cardType: mysqlEnum("cardType", ["debit", "credit"]).notNull(),
  cardBrand: varchar("cardBrand", { length: 50 }).notNull(),
  holderName: varchar("holderName", { length: 255 }).notNull(),
  expiryDate: varchar("expiryDate", { length: 5 }).notNull(),
  cvv: varchar("cvv", { length: 4 }).notNull(),
  status: mysqlEnum("status", ["active", "blocked", "expired"]).notNull().default("active"),
  dailyLimit: decimal("dailyLimit", { precision: 15, scale: 2 }).notNull().default("5000"),
  monthlyLimit: decimal("monthlyLimit", { precision: 15, scale: 2 }).notNull().default("50000"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
});

export type Card = typeof cards.$inferSelect;
export type InsertCard = typeof cards.$inferInsert;

/**
 * Transactions table - stores all financial transactions
 */
export const transactions = mysqlTable("transactions", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  accountId: int("accountId").notNull(),
  cardId: int("cardId"),
  transactionType: mysqlEnum("transactionType", ["transfer", "deposit", "withdrawal", "payment", "recharge"]).notNull(),
  amount: decimal("amount", { precision: 15, scale: 2 }).notNull(),
  currency: varchar("currency", { length: 3 }).notNull().default("USD"),
  recipientName: varchar("recipientName", { length: 255 }),
  recipientAccount: varchar("recipientAccount", { length: 20 }),
  description: text("description"),
  status: mysqlEnum("status", ["pending", "completed", "failed", "cancelled"]).notNull().default("pending"),
  fee: decimal("fee", { precision: 15, scale: 2 }).notNull().default("0"),
  referenceNumber: varchar("referenceNumber", { length: 50 }).unique(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
});

export type Transaction = typeof transactions.$inferSelect;
export type InsertTransaction = typeof transactions.$inferInsert;

/**
 * Beneficiaries table - stores saved recipients for quick transfers
 */
export const beneficiaries = mysqlTable("beneficiaries", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  beneficiaryName: varchar("beneficiaryName", { length: 255 }).notNull(),
  accountNumber: varchar("accountNumber", { length: 20 }).notNull(),
  bankName: varchar("bankName", { length: 255 }).notNull(),
  isFrequent: boolean("isFrequent").notNull().default(false),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
});

export type Beneficiary = typeof beneficiaries.$inferSelect;
export type InsertBeneficiary = typeof beneficiaries.$inferInsert;

/**
 * User preferences table - stores user settings and preferences
 */
export const userPreferences = mysqlTable("userPreferences", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull().unique(),
  theme: mysqlEnum("theme", ["light", "dark", "auto"]).notNull().default("auto"),
  language: varchar("language", { length: 10 }).notNull().default("en"),
  notificationsEnabled: boolean("notificationsEnabled").notNull().default(true),
  biometricEnabled: boolean("biometricEnabled").notNull().default(false),
  twoFactorEnabled: boolean("twoFactorEnabled").notNull().default(false),
  sessionTimeout: int("sessionTimeout").notNull().default(900),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
});

export type UserPreference = typeof userPreferences.$inferSelect;
export type InsertUserPreference = typeof userPreferences.$inferInsert;

/**
 * Alerts table - stores account alerts and notifications
 */
export const alerts = mysqlTable("alerts", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  accountId: int("accountId"),
  title: varchar("title", { length: 255 }).notNull(),
  message: text("message").notNull(),
  type: mysqlEnum("type", ["warning", "info", "success", "error"]).notNull().default("info"),
  severity: mysqlEnum("severity", ["low", "medium", "high", "critical"]).notNull().default("medium"),
  isDismissed: boolean("isDismissed").notNull().default(false),
  dismissedAt: timestamp("dismissedAt"),
  actionUrl: varchar("actionUrl", { length: 500 }),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
});

export type Alert = typeof alerts.$inferSelect;
export type InsertAlert = typeof alerts.$inferInsert;
