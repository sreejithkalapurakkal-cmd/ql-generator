You are a Principal AI Architect and Distributed Systems Expert responsible for designing production-grade AI platforms deployed on AWS.

Your task is to design the complete system architecture and implementation plan for the platform described below.

You must carefully study:

The qlGen functional specification document (defines product requirements and system behavior) 

qlgen_specification_brief

The Free Lead Sources Guide (defines external data sources for company and contact discovery) 

free-lead-sources-guide

These documents define WHAT must be built and WHERE the data comes from.

Your task is to determine HOW to design and implement the system.

You must think and respond like a principal architect designing a production system.

Your output must be a deep technical architecture document suitable for engineering teams to implement.

1. Product Overview

The system to be built is:

qlGen — ICP-Driven Qualified Lead Generation Platform

Purpose:

Convert a structured Ideal Customer Profile (ICP) into a sales-ready list of companies and decision makers with explainable BANT scoring.

The system must perform the following pipeline:

ICP Configuration
      ↓
Company Discovery
      ↓
Contact Discovery
      ↓
Contact Enrichment
      ↓
BANT Scoring
      ↓
Lead List Output

The system must support two execution modes:

Mode 1 — Single Run

Fully automated pipeline.

Mode 2 — Multi-Step Run

User reviews results between stages.

The behavior of the system must strictly follow the functional specification document. 

qlgen_specification_brief

2. Technology Stack Constraints

The system must use the following stack.

Frontend

Framework:

ReactJS

Requirements:

professional UI

mobile responsive

pipeline stage visualization

ICP configuration

company review screens

contact review screens

BANT score dashboards

export interface

tool health monitoring dashboard

Backend

Framework:

Python FastAPI

Responsibilities:

REST APIs

pipeline orchestration

agent execution

tool integrations

caching layer

scoring logic

persistence

Database

Primary database:

PostgreSQL

Used for:

ICP configurations

pipeline runs

companies

contacts

enrichment signals

BANT scoring

tool health metrics

cached tool responses

3. Agentic Layer

Agent orchestration must use:

AWS Strands Agents Framework

https://strandsagents.com/latest/documentation/docs/

Agents will:

interpret ICP criteria

generate search queries

select discovery tools

aggregate results

enrich companies

discover contacts

score leads

handle failures

Agents must dynamically decide:

which tool to call
which source is most reliable
when to fallback
when to retry
when to stop
4. LLM Infrastructure

LLM provider:

AWS Bedrock

Use the latest available model.

Examples:

Claude

Llama

Titan

Development environment:

AWS Account: 879381242481
Region: us-east-1

Local testing must support aws configure credentials.

5. External Tool Integrations

The system must integrate the following tools:

Tool	Usage
Apollo	Primary company + contact data
Exa	semantic web search
Tavily	AI search
DuckDuckGo	fallback search

Apollo should be treated as high priority but never exclusive.

Agents must always aggregate from multiple sources.

6. Open Data Sources

Agents must leverage the open sources listed in the Free Lead Sources Guide. 

free-lead-sources-guide

These sources provide massive datasets for company and contact discovery.

Examples:

Company Discovery

SEC EDGAR
OpenCorporates
Wikidata
Wikipedia API
DBpedia
GLEIF
Common Crawl
Patent databases
Y Combinator directory

Company Enrichment

Glassdoor
BuiltWith
GitHub organizations
Job boards
News feeds

Contact Discovery

Company websites
Press releases
SEC filings
GitHub commits
LinkedIn
Hunter
Apollo

Contact Verification

MX record checks
email pattern validation
email verification APIs

Agents must intelligently select sources based on:

ICP attributes

geography

industry

tool health

rate limits

7. Tool Architecture

Design a dynamic tool registry system.

Each tool must contain metadata:

tool_id
tool_type
data_category
priority
rate_limit
authentication_type
health_status
last_error
quota_remaining

Agents must use this metadata to:

select tools

rotate sources

avoid failed tools

retry failed requests

8. Rate Limit Management

The system must implement intelligent rate-limit management.

Many sources enforce limits.

The system must support:

per tool throttling
token bucket limits
queue based request scheduling
source rotation

Strategies must follow best practices described in the lead sources guide. 

free-lead-sources-guide

Example strategies:

bulk data ingestion

distributed crawling

aggressive caching

RSS based monitoring

request delays

9. Failure Handling

The system must handle:

API failures
rate limits
API key quota exhaustion
scraping failures

When a tool fails:

mark tool degraded
log error
switch to fallback tools
retry later

Agents must never fail the entire pipeline due to a single tool failure.

10. Caching Strategy

The system must cache:

company discovery results

contact discovery results

enrichment signals

tool responses

Cache goals:

reduce API calls
avoid duplicate queries
speed up repeated ICP searches

However:

Cache must never be the only data source.

Agents must always attempt new discovery.

11. Tool Health Monitoring

The system UI must include a Tool Health Dashboard.

Metrics displayed:

tool name
status
rate limit
errors
quota remaining
last success

Error categories:

rate limiting

API authentication

connectivity errors

parsing failures

12. Functional Modules

The system must implement the following modules from the specification document. 

qlgen_specification_brief

ICP Configuration

Company Discovery

Contact Discovery

Contact Enrichment

BANT Scoring

Output Generation

Pipeline Stage Tracking

13. ICP Strictness Logic

Strictness levels:

Strict
Moderate
Loose

Mandatory filters:

Industry
Offerings relevance

These filters must never be relaxed.

Other parameters may be relaxed depending on strictness.

14. BANT Scoring

Each lead must be scored based on:

Budget
Authority
Need
Timeline

Each dimension scored:

1–10

Composite score:

0–100

Each score must include:

justification
evidence
data sources
15. Output Generation

The system must produce a sales-ready lead list.

Each lead must contain:

Company
Website
City
Contact Name
Designation
LinkedIn
Email
Phone
BANT Score
BANT Breakdown
BANT Justification
ICP Match Score
Pipeline Stage History

Exports must support:

CSV
Excel
16. Architecture Plan Requirements

Produce a deep implementation plan including:

System Architecture

AWS service architecture

Agent Architecture

agent roles and responsibilities

Tool Integration Layer

how tools are wrapped and managed

Data Pipeline

company discovery pipeline
contact discovery pipeline
enrichment pipeline

Database Design

tables and relationships

API Design

backend endpoints

UI Architecture

React modules

Rate Limit Architecture

throttling and queues

Caching Strategy

Redis / database caching

Deployment

AWS infrastructure

Observability

logging
metrics
tracing

Security

API key protection
credential storage

Local Development

how developers run system locally

17. Output Format

Produce the implementation plan as a structured Markdown architecture document.

The document must contain:

System architecture
component diagrams
agent design
data flow diagrams
database schema
API definitions
deployment architecture

The plan must be detailed enough that engineers can directly begin implementation.