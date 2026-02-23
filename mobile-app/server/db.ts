import { eq, and, desc, gte, lte } from "drizzle-orm";
import { drizzle } from "drizzle-orm/mysql2";
import { InsertUser, users, accounts, cards, transactions, beneficiaries, userPreferences, InsertAccount, InsertCard, InsertTransaction, InsertBeneficiary, InsertUserPreference } from "../drizzle/schema";
import { ENV } from "./_core/env";

let _db: ReturnType<typeof drizzle> | null = null;

// Lazily create the drizzle instance so local tooling can run without a DB.
export async function getDb() {
  if (!_db && process.env.DATABASE_URL) {
    try {
      _db = drizzle(process.env.DATABASE_URL);
    } catch (error) {
      console.warn("[Database] Failed to connect:", error);
      _db = null;
    }
  }
  return _db;
}

export async function upsertUser(user: InsertUser): Promise<void> {
  if (!user.openId) {
    throw new Error("User openId is required for upsert");
  }

  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot upsert user: database not available");
    return;
  }

  try {
    const values: InsertUser = {
      openId: user.openId,
    };
    const updateSet: Record<string, unknown> = {};

    const textFields = ["name", "email", "loginMethod"] as const;
    type TextField = (typeof textFields)[number];

    const assignNullable = (field: TextField) => {
      const value = user[field];
      if (value === undefined) return;
      const normalized = value ?? null;
      values[field] = normalized;
      updateSet[field] = normalized;
    };

    textFields.forEach(assignNullable);

    if (user.lastSignedIn !== undefined) {
      values.lastSignedIn = user.lastSignedIn;
      updateSet.lastSignedIn = user.lastSignedIn;
    }
    if (user.role !== undefined) {
      values.role = user.role;
      updateSet.role = user.role;
    } else if (user.openId === ENV.ownerOpenId) {
      values.role = "admin";
      updateSet.role = "admin";
    }

    if (!values.lastSignedIn) {
      values.lastSignedIn = new Date();
    }

    if (Object.keys(updateSet).length === 0) {
      updateSet.lastSignedIn = new Date();
    }

    await db.insert(users).values(values).onDuplicateKeyUpdate({
      set: updateSet,
    });
  } catch (error) {
    console.error("[Database] Failed to upsert user:", error);
    throw error;
  }
}

export async function getUserByOpenId(openId: string) {
  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot get user: database not available");
    return undefined;
  }

  const result = await db.select().from(users).where(eq(users.openId, openId)).limit(1);

  return result.length > 0 ? result[0] : undefined;
}

// ============ ACCOUNTS ============

export async function getUserAccounts(userId: number) {
  const db = await getDb();
  if (!db) return [];
  
  return db.select().from(accounts).where(eq(accounts.userId, userId));
}

export async function getAccountById(id: number, userId: number) {
  const db = await getDb();
  if (!db) return undefined;
  
  const result = await db.select().from(accounts).where(and(eq(accounts.id, id), eq(accounts.userId, userId))).limit(1);
  return result.length > 0 ? result[0] : undefined;
}

export async function createAccount(data: InsertAccount) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  await db.insert(accounts).values(data);
}

export async function updateAccount(id: number, userId: number, data: Partial<InsertAccount>) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  await db.update(accounts).set(data).where(and(eq(accounts.id, id), eq(accounts.userId, userId)));
}

// ============ CARDS ============

export async function getUserCards(userId: number) {
  const db = await getDb();
  if (!db) return [];
  
  return db.select().from(cards).where(eq(cards.userId, userId));
}

export async function getCardById(id: number, userId: number) {
  const db = await getDb();
  if (!db) return undefined;
  
  const result = await db.select().from(cards).where(and(eq(cards.id, id), eq(cards.userId, userId))).limit(1);
  return result.length > 0 ? result[0] : undefined;
}

export async function createCard(data: InsertCard) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  await db.insert(cards).values(data);
}

export async function updateCard(id: number, userId: number, data: Partial<InsertCard>) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  await db.update(cards).set(data).where(and(eq(cards.id, id), eq(cards.userId, userId)));
}

// ============ TRANSACTIONS ============

export async function getUserTransactions(userId: number, limit = 50, offset = 0) {
  const db = await getDb();
  if (!db) return [];
  
  return db.select().from(transactions)
    .where(eq(transactions.userId, userId))
    .orderBy(desc(transactions.createdAt))
    .limit(limit)
    .offset(offset);
}

export async function getAccountTransactions(accountId: number, userId: number, limit = 50, offset = 0) {
  const db = await getDb();
  if (!db) return [];
  
  return db.select().from(transactions)
    .where(and(eq(transactions.accountId, accountId), eq(transactions.userId, userId)))
    .orderBy(desc(transactions.createdAt))
    .limit(limit)
    .offset(offset);
}

export async function getTransactionById(id: number, userId: number) {
  const db = await getDb();
  if (!db) return undefined;
  
  const result = await db.select().from(transactions).where(and(eq(transactions.id, id), eq(transactions.userId, userId))).limit(1);
  return result.length > 0 ? result[0] : undefined;
}

export async function createTransaction(data: InsertTransaction) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  await db.insert(transactions).values(data);
}

export async function updateTransaction(id: number, userId: number, data: Partial<InsertTransaction>) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  await db.update(transactions).set(data).where(and(eq(transactions.id, id), eq(transactions.userId, userId)));
}

// ============ BENEFICIARIES ============

export async function getUserBeneficiaries(userId: number) {
  const db = await getDb();
  if (!db) return [];
  
  return db.select().from(beneficiaries).where(eq(beneficiaries.userId, userId));
}

export async function getBeneficiaryById(id: number, userId: number) {
  const db = await getDb();
  if (!db) return undefined;
  
  const result = await db.select().from(beneficiaries).where(and(eq(beneficiaries.id, id), eq(beneficiaries.userId, userId))).limit(1);
  return result.length > 0 ? result[0] : undefined;
}

export async function createBeneficiary(data: InsertBeneficiary) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  await db.insert(beneficiaries).values(data);
}

export async function updateBeneficiary(id: number, userId: number, data: Partial<InsertBeneficiary>) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  await db.update(beneficiaries).set(data).where(and(eq(beneficiaries.id, id), eq(beneficiaries.userId, userId)));
}

export async function deleteBeneficiary(id: number, userId: number) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  await db.delete(beneficiaries).where(and(eq(beneficiaries.id, id), eq(beneficiaries.userId, userId)));
}

// ============ USER PREFERENCES ============

export async function getUserPreferences(userId: number) {
  const db = await getDb();
  if (!db) return undefined;
  
  const result = await db.select().from(userPreferences).where(eq(userPreferences.userId, userId)).limit(1);
  return result.length > 0 ? result[0] : undefined;
}

export async function createUserPreferences(data: InsertUserPreference) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  await db.insert(userPreferences).values(data);
}

export async function updateUserPreferences(userId: number, data: Partial<InsertUserPreference>) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  await db.update(userPreferences).set(data).where(eq(userPreferences.userId, userId));
}
