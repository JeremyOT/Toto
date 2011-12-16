CREATE TABLE `account` (
  `account_id` int(8) unsigned NOT NULL AUTO_INCREMENT,
  `password` char(64) DEFAULT NULL,
  `user_id` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`account_id`),
  UNIQUE KEY `account_id_UNIQUE` (`account_id`)
);

CREATE TABLE `session` (
  `session_id` char(32) NOT NULL,
  `account_id` int(8) unsigned NOT NULL,
  `expires` datetime NOT NULL,
  `state` blob,
  PRIMARY KEY (`session_id`),
  UNIQUE KEY `session_id_UNIQUE` (`session_id`),
  INDEX (`account_id`),
  FOREIGN KEY (`account_id`) REFERENCES `account`(`account_id`)
);
