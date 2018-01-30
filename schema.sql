drop table if exists user;

create table user (
  user_id int AUTO_INCREMENT,
  username varchar(100) NOT NULL,
  email varchar(100) NOT NULL,
  pw_hash varchar(100),
  PRIMARY KEY (user_id)
);

drop table if exists follower;
create table follower (
  who_id int,
  whom_id int
);

drop table if exists message;
create table message (
  message_id intAUTO_INCREMENT,
  author_id int NOT NULL,
  text text NOT NULL,
  pub_date int,
  PRIMARY KEY (message_id)
);

