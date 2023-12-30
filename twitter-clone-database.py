import sqlite3
import os
import time
import hashlib
import getpass
from datetime import datetime

connection = None
cursor = None
current_user = None # global to maintain who is logged in

# connects user to database
def connect(path): 
    global connection, cursor

    connection = sqlite3.connect(path)
    cursor = connection.cursor()
    cursor.execute('PRAGMA foreign_keys=ON;') # enables foreign key constraints
    connection.commit()

# checks if a user exists in the database, returns a boolean
def user_exists(user_id):
    global connection, cursor

    user_id = user_id.lower() # case insensitive
    # query to search for the user ID in the database
    query = "SELECT * FROM users WHERE LOWER(usr) = ?"  # makes the search case insensitive
    cursor.execute(query, (user_id,))
    user_data = cursor.fetchone()
    return bool(user_data)

# checks if the password entered is in the database, returns a boolean
def correct_password(user_id, password):
    global connection, cursor

    user_id = user_id.lower() # case insensitive user
    # query to search for the user ID and its password in the database
    query = "SELECT * FROM users WHERE LOWER(usr) = ? AND pwd=?" # makes the search for the user case insensitive, not the password
    cursor.execute(query, (user_id, password))
    user_data = cursor.fetchone()
    return bool(user_data)

# prints a tweet and its details, returns nothing
def print_tweet(tweet_id):
    global connection, cursor

    # query to find the specific tweet in the database
    cursor.execute("SELECT * FROM tweets WHERE tid = ?", (tweet_id,))
    tweet = cursor.fetchone()
    if tweet: # if the tweet exists, it prints
        tid, writer, tdate, text, replyto = tweet
        print("\n")
        print(f"Tweet ID: {tid}")
        print(f"Writer: User ID {writer}")
        print(f"Date: {tdate}")
        print(f"Text: {text}")
        if replyto is not None:
            print(f"Reply to Tweet ID: {replyto}")
    else: # error message prints if the tweet does not exist in the database
        print(f"Tweet with ID {tweet_id} not found.")

# displays the tweets and retweets of a user when they log in, returns nothing
def display_following_tweets(user_id, page, tweets_per_page=5):
    user_id = user_id.lower() # case insensitive user search
    # query to find the tweets and retweets of the users who the current user is following
    query = """SELECT t.tid, t.writer, t.tdate, t.text, 'tweet' as tweet_type, NULL as retweeted_by
               FROM tweets t
               WHERE t.writer IN (
                   SELECT flwee
                   FROM follows
                   WHERE LOWER(flwer) = :current_user_id
               )
               UNION
               SELECT r.tid, t.writer as original_writer, t.tdate as original_date, t.text as original_text, 'retweet' as tweet_type, r.usr as retweeted_by
               FROM retweets r
               INNER JOIN tweets t ON r.tid = t.tid
               WHERE r.usr IN (
                   SELECT flwee
                   FROM follows
                   WHERE LOWER(flwer) = :current_user_id
               )
               ORDER BY tdate DESC;
            """
    cursor.execute(query, {"current_user_id": user_id})
    following_tweets = cursor.fetchall()
    if not following_tweets: # checks if following_tweets is empty (no tweets from following)
        print("No tweets from users you're following.")
    else: # find the number of tweets, initialize the start index and the end index
        num_tweets = len(following_tweets)
        start_index = (page - 1) * tweets_per_page
        end_index = start_index + tweets_per_page
        if start_index >= num_tweets: # prints a message when all the tweets have been shows
            print("\nNo more tweets to display.\n")
        else:
            print("Home Feed\nTweets from users you're following:\n")
            for tweet in following_tweets[start_index:end_index]:
                tweet_id, writer_id, tweet_date, tweet_text, tweet_type, retweeted_by = tweet
                # format and print tweet with the type, original writer, and retweeter (if available)
                print(f"Tweet Type: {tweet_type.capitalize()}")
                print(f"Tweet ID: {tweet_id}")
                if tweet_type == 'retweet':
                    print(f"Original Writer: {writer_id}")
                    print(f"Retweeted by: {retweeted_by}")
                else:
                    print(f"Writer: {writer_id}")
                print(f"Date: {tweet_date}")
                print(f"Text: {tweet_text}")
                print()
            if end_index < num_tweets: # if there are still more tweets available, a message prints to allow the user to see more tweets
                print(f"More tweets on the next page -> (Page {page + 1}).")

# allows user to search for tweets using keywords and hashtags, returns search_results
def search_tweets(page, prev_key, search_results=None):
    global connection, cursor, prev_keywords

    # ask the user to input keywords only on the first page
    if page == 1: 
        if prev_key == 1: # indicates there are previous keys to be searched (allows the user to go back to their search results if they perform an action)
            keywords = prev_keywords
            words = keywords.split()
        else:
            keywords = input("Enter one or more keywords. Please leave a space between each keyword if there are multiple keywords: ")
            words = keywords.split()

        prev_keywords = keywords 
        result = []
        for word in words:
            word = word.lower() # case insensitive search for keywords

            if word[0] == '#': # if there is a hashtag in the tweet
                new_word = word[1:]
                # query to find all tweets that have the same hashtag to what is being searched for (case insensitive)
                query = """SELECT m.tid, t.writer, t.tdate, t.text, t.replyto 
                        FROM mentions m 
                        JOIN tweets t ON m.tid = t.tid 
                        WHERE LOWER(m.term) LIKE ? 
                        ORDER BY t.tdate DESC;"""
                cursor.execute(query, ('%' + new_word + '%', ))
            else: # find tweets who have a word similar to what is being searched for
                new_word = "%" + word + "%"
                query = "SELECT * FROM tweets WHERE LOWER(text) LIKE ? ORDER BY tdate DESC;"
                cursor.execute(query, (new_word, ))

            query_result = cursor.fetchall()
            result += query_result # append to results
        # sort the results
        sorted_results = sorted(result, key=lambda tup: tup[2], reverse=True)
        # remove duplicates (make it a set) and re-sort by tweet date
        search_results = list(set(sorted_results))
        search_results = sorted(search_results, key=lambda tup: tup[2], reverse=True)

    # define the number of tweets per page (tweets we show at a time)
    tweets_per_page = 5

    # calculate the range of tweets to display on the current page
    start_tweet = (page - 1) * tweets_per_page
    end_tweet = start_tweet + tweets_per_page

    # check if there are no matching tweets
    if len(search_results) == 0:
        print("No matching tweets found.")
        return search_results 

    # display the results for the current page
    for result in search_results[start_tweet:end_tweet]:
        print("Tweet ID:", result[0])
        print("Writer:", result[1])
        print("Tweet Date:", result[2])
        print("Text:", result[3])
        if result[4] is not None: # checks if the tweet is a reply and prints the tweet it replies to if it is
            print("Reply To:", result[4])
        print("\n")

    return search_results # returns the updated search_results so they can be passed to the next page


# shows tweet details for a specified tweet, returns nothing
def tweet_stats(tweet_id):
    global connection, cursor

    # query to find the number of replies
    query1 = "SELECT COUNT(*) FROM tweets WHERE replyto = ?;"
    cursor.execute(query1, (tweet_id, ))
    reply_count = cursor.fetchone()[0]

    # query to find the number of retweets
    query2 = "SELECT COUNT(*) FROM retweets WHERE tid = ?;"
    cursor.execute(query2, (tweet_id, ))
    retweet_count = cursor.fetchone()[0]

    # print the tweet and its stats
    print_tweet(tweet_id) 
    print("Retweet Count: ", retweet_count)
    print("Reply Count: ", reply_count)
    print("\n")


# allows a user to retweet a given tweet, returns nothing
def retweet(user_id, tweet_id):
    global connection, cursor

    # validate the input, checks if the tweet id is an integer
    if not tweet_id.isdigit():
        print("Invalid input - tweet ID should be a number. Please try again.")
        return

    # query to check if the tweet id is valid and exists in the database
    cursor.execute("SELECT * FROM tweets WHERE tid = ?", (tweet_id,))
    tweet = cursor.fetchone()
    if tweet is None:
        print("Invalid tweet ID. Please try again.")
        return

    # query which keeps a user a user from retweeting the same tweet more than once
    cursor.execute("SELECT * FROM retweets WHERE usr = ? AND tid = ?", (user_id, tweet_id))
    retweet = cursor.fetchone()
    if retweet is not None:
        print("You have already retweeted this tweet. Please try again.")
        return

    # display the tweet that we want to retweet
    print("Retweeting:")
    print_tweet(tweet_id)

    # query to insert the retweet into the retweets table
    retweet_date = time.strftime('%Y-%m-%d')  # get current date in YYYY-MM-DD format
    cursor.execute("INSERT INTO retweets (usr, tid, rdate) VALUES (?, ?, ?)", (user_id, tweet_id, retweet_date))
    
    connection.commit()

    print("Successfully retweeted!\n") # success message


def reply_to(user_id, tweet_id):
    global connection, cursor

    # query to check if the tweet_id is valid and exists in the database
    cursor.execute("SELECT * FROM tweets WHERE tid = ?", (tweet_id,))
    tweet = cursor.fetchone()
    if tweet is None:
        print("Invalid tweet ID. Please try again.")
        return
    
    # display the tweet the user wants to reply to
    print("Replying to: ")
    print_tweet(tweet_id)
    
    # compose the reply
    reply_text = input("Compose your reply: ").strip()
    if not reply_text: # ensure the reply text is not empty
        print("Reply cannot be empty. Please try again.")
        return

    # insert the reply into the tweets table
    reply_date = time.strftime('%Y-%m-%d') # get current date in YYYY-MM-DD format
    reply_tweet_id = cursor.execute("SELECT MAX(tid) FROM tweets").fetchone()[0] + 1 # get the next available tweet ID
    cursor.execute("INSERT INTO tweets (writer, tdate, text, replyto, tid) VALUES (?, ?, ?, ?, ?)", (user_id, reply_date, reply_text, tweet_id, reply_tweet_id))

    # parse the reply text for hashtags
    hashtags = set(part[1:] for part in reply_text.split() if part.startswith("#")) 
    for hashtag in hashtags:
        hashtag_lower = hashtag.lower()
        # check if the hashtag is already in the hashtags table
        cursor.execute("SELECT term FROM hashtags WHERE LOWER(term) = ?", (hashtag_lower,))
        existing_hashtag = cursor.fetchone()

        if existing_hashtag is None:  # if the hashtag does not exist, insert it
            cursor.execute("INSERT INTO hashtags (term) VALUES (?)", (hashtag,))

        # insert reply into mentions if a hashtag is used
        cursor.execute("INSERT INTO mentions (tid, term) VALUES (?, ?)", (reply_tweet_id, hashtag))
        
    connection.commit()
    print("Reply posted successfully!\n") # success message


# allows users to search for other users using a keyword, returns search_results
def search_users(page, user_key, search_results=None): # this has an injection attack risk
    global connection, cursor, user_keyword
    if user_key == 1:
        keyword = user_keyword
    else:
    # asks user to input keywords, leaving a space in between multiple keywords
        keyword = input("Enter a keyword: ")
    user_keyword = keyword
    keyword = keyword.strip().lower()
    keyword = "%" + keyword + "%"

    result = []

    query1 = "SELECT * FROM users WHERE name LIKE ? ORDER BY LENGTH(name) ASC;"
    cursor.execute(query1, (keyword, ))
    result += cursor.fetchall()

    query2 = "SELECT * FROM users WHERE city LIKE ? AND name NOT LIKE ? ORDER BY LENGTH(city) ASC;"
    cursor.execute(query2, (keyword, keyword, ))

    result += cursor.fetchall()
    # remove duplicates
    search_results = (result)
    # Remove duplicates while preserving order
    search_results = []
    seen = set()
    filtered = []
    for item in result:
        if item not in seen:
            filtered.append(item)
            seen.add(item)
    #search_results = sorted(search_results, key=lambda tup: tup[2], reverse=True)

    # Define the page size (number of tweets per page)
    tweets_per_page = 5

    # Calculate the range of tweets to display on the current page
    start_tweet = (page - 1) * tweets_per_page
    end_tweet = start_tweet + tweets_per_page

    # Check if there are no matching tweets
    if len(filtered) == 0:
        print("No matching users found.")
        return search_users(page, user_key, search_results)  # Return the same search_results

    # Display the results for the current page, idk what we want to show
    for result in filtered[start_tweet:end_tweet]:
        print("User ID:", result[0])
        print("Name:", result[2])
        print("City:", result[4])
        print("\n")

    return filtered
# allows a user to write their own original tweet
def compose_tweet(user_id):
    tweet_text = input("Compose your tweet: ").strip() # strip() removes leading and trailing whitespaces

    # check if the tweet is empty, cannot post an empty tweet
    if not tweet_text:
        print("\nTweet cannot be empty. Please try again.\n")
        return

    user_id = user_id.lower() # case insensitive user lookup
    tweet_date = time.strftime('%Y-%m-%d') # get current date in YYYY-MM-DD format
    tweet_id = cursor.execute("SELECT MAX(tid) FROM tweets").fetchone()[0] 
    # query to insert tweet into tweets
    cursor.execute("INSERT INTO tweets (tid, writer, tdate, text) VALUES (?, ?, ?, ?)", (tweet_id + 1, user_id, tweet_date, tweet_text))

    # handles if the tweet has hashtags by parsing the tweet text for hashtags
    hashtags = set(part[1:] for part in tweet_text.split() if part.startswith("#")) 
    for hashtag in hashtags:
        hashtag_lower = hashtag.lower()
        cursor.execute("SELECT term FROM hashtags WHERE LOWER(term) = ?", (hashtag_lower,))
        existing_hashtag = cursor.fetchone()

        if existing_hashtag is None: # if the hashtag doesn't exist, insert it
            cursor.execute("INSERT INTO hashtags (term) VALUES (?)", (hashtag,))
            
        cursor.execute("INSERT INTO mentions (tid, term) VALUES (?, ?)", (tweet_id, hashtag))

    connection.commit()
    print("Tweet posted successfully!\n") # success message


# prints a specified user's information, returns nothing
def user_info(selected_user_id):
    global connection, cursor

    # query to get details of specified user
    query = """
    SELECT name,
    (SELECT COUNT(*) FROM tweets WHERE writer = usr) as tweet_count,
    (SELECT COUNT(*) FROM follows WHERE flwer = usr) as following_count,
    (SELECT COUNT(*) FROM follows WHERE flwee = usr) as followers_count
    FROM users
    WHERE usr = ?;
    """
    cursor.execute(query, (selected_user_id,))
    user_data = cursor.fetchone()

    if user_data is None: # checks if user exists
        print("User not found.")
        return
    username, tweet_count, following_count, followers_count = user_data

    # prints user information if the user exists
    print(f"\nDetails for User ID {selected_user_id}:")
    print(f"User ID: {username}")
    print(f"Number of Tweets: {tweet_count}")
    print(f"Following: {following_count}")
    print(f"Followers: {followers_count}")


# lists the current user's followers, returns nothing
def list_followers(current_user_id):
    global connection, cursor

    # query to retrieve all users who follow the current user
    query = """
    SELECT u.usr, u.name
    FROM follows f
    JOIN users u ON f.flwer = u.usr
    WHERE LOWER(f.flwee) = LOWER(?)
    """
    cursor.execute(query, (current_user_id,))
    followers = cursor.fetchall()
    
    if not followers: # checks if the user has followers
        print("\nYou have no followers.\n")
        return
    
    print("Your followers:")
    for username, user_id in followers:
        print(username) # prints user_ids

    # give the option to view more details about a follower or exit
    while True:
        selected_user_id = input("\nEnter a follower's user ID to view more details (or type 'exit' to go back): ")
        if selected_user_id.lower() == 'exit':
            break
        else:
            view_user_details(selected_user_id, current_user_id)
            break


# displays a user's details, including their 3 most recent tweets, returns nothing
def view_user_details(selected_user_id, current_user_id):
    global connection, cursor

    user_info(selected_user_id)

    # query to get and display the 3 most recent tweets
    query = """
    SELECT tdate, text
    FROM tweets
    WHERE writer = ?
    ORDER BY tdate DESC
    LIMIT 3
    """
    cursor.execute(query, (selected_user_id,))
    recent_tweets = cursor.fetchall()

    print("\n3 Most Recent Tweets:")
    # checks if there are recent tweets and prints if there are no tweets at all
    if not recent_tweets:
        print("No tweets available.")
    else:
        for date, text in recent_tweets:
            print("Text: ", text)
            print("Date: ", date)

    # give the option to follow the user or see more tweets
    while True:
        action = input("\n(1) Follow User\n(2) See More Tweets\n(3) Go Back\nOption:")
        if action == '1':
            follow_user(current_user_id, selected_user_id)
            list_followers(current_user_id)
            break
        elif action == '2':
            see_more_tweets(selected_user_id)
            break
        elif action == '3':
            list_followers(current_user_id)
            break
        else:
            print("Invalid input. Please enter 1, 2, or 3.")


# allows the current user to follow another user
def follow_user(current_user_id, followee_id):
    global connection, cursor

    # query to check if the user is already following the followee
    query = "SELECT * FROM follows WHERE flwer = ? AND flwee = ?"
    cursor.execute(query, (current_user_id, followee_id))
    if cursor.fetchone():
        print("You are already following this user.")
        return
    
    # ensure that the user cannot follow themselves
    if current_user_id == followee_id:
        print("You cannot follow yourself.")
        return

    current_datetime = time.strftime('%Y-%m-%d') # get the current date
    # query to insert the following relationship into the follows table
    query = "INSERT INTO follows (flwer, flwee, start_date) VALUES (?, ?, ?)"
    cursor.execute(query, (current_user_id, followee_id, current_datetime))
    connection.commit()
    print("You are now following this user.") # success message


# allows the current user to see the next 3 most recent tweets of a selected user
def see_more_tweets(user_id):
    global connection, cursor

    # query to get and display 3 more tweets from the user
    query = """
    SELECT tdate, text
    FROM tweets
    WHERE writer = ?
    ORDER BY tdate DESC
    LIMIT -1 OFFSET 3;
    """
    cursor.execute(query, (user_id,))
    additional_tweets = cursor.fetchall()

    # checks if no more tweets are available, prints if there are
    if not additional_tweets:
        print("No more tweets available.")
    else:
        for date, text in additional_tweets:
            print("Text: ", text)
            print("Date: ", date)


# logs the current user out
def logout():
    global current_user
    print("Logging out...") # logout message
    current_user = None # sets the current user to None
    login_screen() # goes back to login screen


# allows the current user to perform actions on a tweet
def tweet_actions(user_id, tweet_id):
    tweet_stats(tweet_id) # prints the selected tweet
    while True:
        user_input = input("(1) Reply\n(2) Retweet\n(3) Main Menu Actions\nOption: ")
        if user_input == '1': # if the user wants to reply
            reply_to(user_id, tweet_id)
            break
        elif user_input == '2': # if the user wants to retweet
            retweet(user_id, tweet_id)
            break
        elif user_input == '3': # brings the current user back to menu
            break
        else: 
             print("Invalid input. Please enter 1, 2, or 3.") # ensures that there is valid input


# allows the current user to perform actions on another user
def user_actions(selected_user_id, current_user_id):
    while True:
        user_input = input("(1) Follow User\n(2) See More Tweets\n(3) Main Menu Actions\nOption: ")
        if user_input == '1': # allows current user to follow the selected user
            follow_user(selected_user_id, current_user_id)
            break
        elif user_input == '2': # allows current user to see 3 more of the users recent tweets
            see_more_tweets(selected_user_id)
            break
        elif user_input == '3': # brings the current user back to menu
            break
        else: 
            print("Invalid input. Please enter 1, 2, or 3.") # ensures valid input


# main control hub for user actions
def menu(user_id):
    global current_user
    prev_key = 0
    user_key = 0
    search_results = []  # initialize an empty list to store search results
    page = 1  # initialize the page number outside of the loop
    while True:
        user_input = input(
            f"Main Menu\nPlease choose an action from those provided below:"
            f"\n(1) Search Tweets\n(2) Write a Tweet\n(3) Search Users\n(4) See Followers\n(5) Logout\nOption: "
        )
        # if the user chooses to search for other users
        if user_input == '1':
            while True:
                # call search_tweets with the current page and search results
                search_results = search_tweets(page, prev_key, search_results)
                prev_key = 1
                if len(search_results) == 0:
                    break
                user_input = input("(1) More Tweets\n(2) Get Tweet Details, Reply, or Retweet\n(3) Main Menu Actions\nOption: ")
                while user_input not in ['1', '2', '3']:
                    print("Invalid input. Please enter 1, 2, or 3.")
                    user_input = input("(1) More Tweets\n(2) Get Tweet Details, Reply, or Retweet\n(3) Main Menu Actions\nOption: ")
                if user_input == '1':
                    page += 1
                    # check if there are more pages to show
                    if (page - 1) * 5 >= len(search_results):
                        print("\nNo more tweets to show.\n")
                elif user_input == '2':
                    tweet_id = input("Please enter the tweet id: ")
                    tweet_actions(current_user, tweet_id)
                    continue
                elif user_input == '3':
                    prev_key = 0
                    page = 1
                    break
                else:
                    print("Invalid input. Please enter 1, 2, or 3.") # ensures valid input
        
        # if the user chooses to write a tweet
        elif user_input == '2':
            compose_tweet(user_id)

        # if the user chooses to search for other users
        elif user_input == '3':
            while True:
                search_results = search_users(page, user_key, search_results)
                user_key = 1
                if len(search_results) == 0:
                    break
                user_input = input("(1) More Users\n(2) Get User Details\n(3) Main Menu Actions\nOption: ")
                if user_input == '1':
                    page += 1
                    # check if there are more pages to show
                    if (page - 1) * 5 >= len(search_results):
                        print("\nNo more users to show.\n")
                elif user_input == '2':
                    selected_user_id = input("Please enter the user id: ")
                    user_info(selected_user_id)
                    user_actions(selected_user_id, current_user)
                    continue
                elif user_input == '3':
                    page = 1
                    user_key = 0
                    break
                else:
                    print("Invalid input. Please enter 1, 2, or 3.")

        # if the user chooses to see who is following them
        elif user_input == '4':
            list_followers(user_id)
        
        # if the user chooses to log out
        elif user_input == '5':
            logout()
            break
        else:
            print("Invalid input. Please enter from the inputs above.\n") # ensures valid input for menu


# if the current user is an existing user, logs them in returns a boolean
def login_user():
    global current_user
    existing_password = ""
    invalid = False
    existing_user = input("\nPlease enter User ID: ")
    # checks if user_id is in existing users in the usrs table
    if user_exists(existing_user):
        # asks for password if successful (make it non-visible using getpass)
        while not correct_password(existing_user, existing_password):
            existing_password = getpass.getpass("Enter your password: ")
            if correct_password(existing_user, existing_password):
                break 
            else:
                print("Wrong password, try again.") # prompts until password is correct
        page = 1
        current_user = existing_user # sets current user to user that is logged in
        while True:
            display_following_tweets(existing_user, page) # displays the tweets of the users they are following
            user_input = input("(1) More Tweets\n(2) Get Tweet Details, Reply, or Retweet\n(3) Main Menu Actions\nOption: ")
            # if the current user wants to see more tweets
            if user_input == '1': 
                page += 1
            # if the user wants to see more details of a tweet
            elif user_input == '2':
                tweet_id = input("Please enter the tweet id: ")
                tweet_actions(current_user, tweet_id)
                continue
            # if the user wants to go back to menu
            elif user_input == '3':
                menu(existing_user)
                break
            else:
                print("Invalid input. Please enter 1, 2, or 3.") # ensures valid input
    # if not in users table ask user to either sign up or exit, redirects to login screen
    else: 
        invalid = True
        print(f"\nUser '{existing_user}' does not exist in the database. Please try again, Sign Up, or Exit. Redirecting...\n")
    return invalid


# if the current user is a new user, it creates adds them to the database, returns nothing
def register_user():
    while True:
        new_user = input("\nPlease create a user_id: ")
        # checks if their user id is unique, error message if it already exists
        if user_exists(new_user):
            print("Username already exists. Please choose a different user_id.")
        # prompt for personal information
        else:
            new_pwd = getpass.getpass("\nPlease create a password: ")
            new_name = input("\nWhat is your name?: ")
            new_email = input("\nWhat is your email?: ")
            new_city = input("\nWhat is your city?: ")
            new_timezone = input("\nWhat is your timezone?: ")
            cursor.execute("INSERT INTO users (usr, pwd, name, email, city, timezone) VALUES (?, ?, ?, ?, ?, ?)", (new_user, new_pwd, new_name, new_email, new_city, new_timezone))
            connection.commit()
            print("\nUser registered successfully.\n")

            current_user = new_user

            break  # exit the loop if registration is successful
    menu(new_user) # brings user to menu by default since they are a new user


# login screen when the program is first opened
def login_screen():
    invalid_input = True
    options = ('1','2','3')
    while invalid_input:
        user_input = input(
                        f"Welcome! Please type in an option from those listed below:\n"
                        f"\n(1) Login - for existing users\n"
                        f"(2) Sign Up - for new users\n"
                        f"(3) Exit - to exit the application\n"
                        f"\nOption: "
        )
        # checks if user input is valid
        if user_input in options: 
            invalid_input = False
            # if the user chooses "Login" as an existing user
            if user_input == '1': 
                invalid_input = login_user()
            # if the user chooses "Sign Up" to register
            elif user_input == '2': 
                register_user()
            # if the user chooses "Exit", terminate the program
            else: 
                print("\nExiting... Goodbye!")
                break
        else:
            print("\nInvalid option, please try again.\n") # invalid input message
    return


# main
def main():
    global connection, cursor, prev_keywords, user_keyword
    prev_keywords = ""
    db_name = input("Please enter the database name (e.g., databasename.db): ")
    path = f"./{db_name}" # assigns path to given database to connect
    # checks if file is valid
    if os.path.isfile(path):
        connect(path)
    else:
        print("Invalid file.") # if file is invalid (does not exist), terminate program
        return
    
    login_screen()

    connection.commit()
    connection.close()
    return

if __name__ == "__main__":
    main()
