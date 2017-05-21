'''
This program pulls comments from reddit for further analysis using natural language processing
Author Sombiri Enwemeka
'''
import sys
import os
sys.path.append(os.path.join(os.getcwd(), '..'))
import watson_developer_cloud
import watson_developer_cloud.natural_language_understanding.features.v1 as features
import praw
import json
import argparse


def main():
    '''
    Main script execution
    '''
    parser = argparse.ArgumentParser(description='Analyze reddit comments')
    parser.add_argument('-r', help='refresh site data')

    args = parser.parse_args()

    print args

    api_keys = None
    with open('../apiKeys.json', 'r') as fp:
        api_keys = json.load(fp)

    # Get all comment text from top n subreddit posts
    reddit = praw.Reddit(
        client_id=api_keys['reddit'][0],
        client_secret=api_keys['reddit'][1],
        user_agent=api_keys['reddit'][2])
    subreddit = reddit.subreddit("the_donald")
    all_comment_text = []
    subm = 0
    watson_nlu = {
        "url": "https://gateway.watsonplatform.net/natural-language-understanding/api",
        "username": api_keys['watson'][0],
        "password": api_keys['watson'][1]}
    nlu = watson_developer_cloud.NaturalLanguageUnderstandingV1(
        version='2017-02-27',
        username=watson_nlu["username"],
        password=watson_nlu["password"])
    for submission in subreddit.top(time_filter='all', limit=5):
        submission.comments.replace_more(limit=0)
        all_comment_text.append(submission.title + "\r\n")
        all_comment_text[subm] += submission.url + "\r\n"
        for comment in submission.comments.list():
            all_comment_text[subm] += comment.body

    # Analyze one of the entries
    response = nlu.analyze(text=all_comment_text[0], features=[features.Entities(), features.Keywords()])
    import ipdb
    ipdb.set_trace()

if __name__ == "__main__":
    main()
