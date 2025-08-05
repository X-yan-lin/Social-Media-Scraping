# Social-Media-Scraping

## Project Background  
This project was developed to collect and analyze marketing-relevant user-generated content about the electric vehicle brand **NIO** on the social media platform **RedNote**. The goal is to support sentiment and engagement analysis for brand-related posts.

## Methodology  
The scraper was designed to extract the **top 100 posts** related to the keyword **“NIO”** using RedNote’s public search interface. Each post's metadata and content elements were collected and structured for analysis.

## About the Files  
The output is saved in an Excel file (`.xlsx`) and includes the following columns:

- `Post URL` – Direct link to the original post  
- `Author Name` – Username of the content creator  
- `Number of Likes` – Total likes on the post  
- `Number of Comments` – Total comments on the post  
- `Post Title` – Title of the post (if available)  
- `Caption` – Full post text or description  
- `Date Published` – Original posting date  
- `Video URL` – Link to embedded video content (if applicable)  
- `User URL` – Link to the author’s profile page  
- `Images URL` – One or more links to images included in the post  

Scripts in this repository automate the scraping, parsing, and file export processes.

