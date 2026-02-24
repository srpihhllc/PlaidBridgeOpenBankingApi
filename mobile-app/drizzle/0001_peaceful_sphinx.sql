CREATE TABLE `accounts` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`accountNumber` varchar(20) NOT NULL,
	`accountType` enum('checking','savings','investment') NOT NULL,
	`accountName` varchar(255) NOT NULL,
	`balance` decimal(15,2) NOT NULL DEFAULT '0',
	`currency` varchar(3) NOT NULL DEFAULT 'USD',
	`status` enum('active','frozen','closed') NOT NULL DEFAULT 'active',
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `accounts_id` PRIMARY KEY(`id`),
	CONSTRAINT `accounts_accountNumber_unique` UNIQUE(`accountNumber`)
);
--> statement-breakpoint
CREATE TABLE `beneficiaries` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`beneficiaryName` varchar(255) NOT NULL,
	`accountNumber` varchar(20) NOT NULL,
	`bankName` varchar(255) NOT NULL,
	`isFrequent` boolean NOT NULL DEFAULT false,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `beneficiaries_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `cards` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`accountId` int NOT NULL,
	`cardNumber` varchar(20) NOT NULL,
	`cardType` enum('debit','credit') NOT NULL,
	`cardBrand` varchar(50) NOT NULL,
	`holderName` varchar(255) NOT NULL,
	`expiryDate` varchar(5) NOT NULL,
	`cvv` varchar(4) NOT NULL,
	`status` enum('active','blocked','expired') NOT NULL DEFAULT 'active',
	`dailyLimit` decimal(15,2) NOT NULL DEFAULT '5000',
	`monthlyLimit` decimal(15,2) NOT NULL DEFAULT '50000',
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `cards_id` PRIMARY KEY(`id`),
	CONSTRAINT `cards_cardNumber_unique` UNIQUE(`cardNumber`)
);
--> statement-breakpoint
CREATE TABLE `transactions` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`accountId` int NOT NULL,
	`cardId` int,
	`transactionType` enum('transfer','deposit','withdrawal','payment','recharge') NOT NULL,
	`amount` decimal(15,2) NOT NULL,
	`currency` varchar(3) NOT NULL DEFAULT 'USD',
	`recipientName` varchar(255),
	`recipientAccount` varchar(20),
	`description` text,
	`status` enum('pending','completed','failed','cancelled') NOT NULL DEFAULT 'pending',
	`fee` decimal(15,2) NOT NULL DEFAULT '0',
	`referenceNumber` varchar(50),
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `transactions_id` PRIMARY KEY(`id`),
	CONSTRAINT `transactions_referenceNumber_unique` UNIQUE(`referenceNumber`)
);
--> statement-breakpoint
CREATE TABLE `userPreferences` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`theme` enum('light','dark','auto') NOT NULL DEFAULT 'auto',
	`language` varchar(10) NOT NULL DEFAULT 'en',
	`notificationsEnabled` boolean NOT NULL DEFAULT true,
	`biometricEnabled` boolean NOT NULL DEFAULT false,
	`twoFactorEnabled` boolean NOT NULL DEFAULT false,
	`sessionTimeout` int NOT NULL DEFAULT 900,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `userPreferences_id` PRIMARY KEY(`id`),
	CONSTRAINT `userPreferences_userId_unique` UNIQUE(`userId`)
);
