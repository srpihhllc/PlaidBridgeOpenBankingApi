CREATE TABLE `alerts` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`accountId` int,
	`title` varchar(255) NOT NULL,
	`message` text NOT NULL,
	`type` enum('warning','info','success','error') NOT NULL DEFAULT 'info',
	`severity` enum('low','medium','high','critical') NOT NULL DEFAULT 'medium',
	`isDismissed` boolean NOT NULL DEFAULT false,
	`dismissedAt` timestamp,
	`actionUrl` varchar(500),
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `alerts_id` PRIMARY KEY(`id`)
);
