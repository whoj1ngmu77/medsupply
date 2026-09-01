"""CAP theorem and document-database characteristics, grounded in
this project's actual architecture."""

CAP_ANALYSIS = {
    "theorem": ("Brewer's CAP theorem: a distributed data store cannot "
                "simultaneously guarantee Consistency, Availability, and "
                "Partition tolerance. Since network partitions are a fact "
                "of distributed systems rather than a design choice, the "
                "real decision is C vs A when a partition occurs."),
    "properties": [
        {"letter": "C", "name": "Consistency",
         "meaning": "Every read returns the most recent committed write."},
        {"letter": "A", "name": "Availability",
         "meaning": "Every request receives a non-error response, though "
                    "possibly stale."},
        {"letter": "P", "name": "Partition tolerance",
         "meaning": "The system continues operating despite dropped or "
                    "delayed messages between nodes."},
    ],
    "postgresql": {
        "classification": "CP (as deployed: single node, so CA in practice)",
        "why": ("MedSupply runs PostgreSQL as a single node, where CAP does "
                "not strictly apply — there is nothing to partition. In a "
                "replicated deployment with synchronous_commit=remote_apply, "
                "it becomes CP: on partition it refuses writes rather than "
                "diverge."),
        "used_for": ["inventory batches", "emergency requests", "allocations",
                     "shipments", "users"],
        "justification": ("Allocating scarce medicine is a consistency "
                          "problem. A stale read means a hospital is "
                          "promised stock that another hospital already "
                          "received. Availability is worth sacrificing; "
                          "correctness is not."),
    },
    "mongodb": {
        "classification": "CP by default, tunable toward AP",
        "why": ("A MongoDB replica set with w:majority and readConcern "
                "majority is CP — a minority partition rejects writes. "
                "Relaxing to w:1 with readPreference secondaryPreferred "
                "moves it toward AP: reads keep succeeding from secondaries "
                "but may be stale."),
        "used_for": ["emergency incident records", "incident timelines"],
        "justification": ("An incident report read five seconds stale is "
                          "operationally harmless. Schema flexibility and "
                          "write availability during a crisis matter more "
                          "than strict consistency."),
    },
    "the_split": ("PostgreSQL where consistency is non-negotiable; MongoDB "
                  "where schema is unpredictable and staleness is tolerable. "
                  "Neither database is being used decoratively."),
    "cost_acknowledged": ("The boundary is not free: emergency_request."
                          "incident_id references a MongoDB ObjectId that "
                          "PostgreSQL cannot enforce as a foreign key. "
                          "Referential integrity across the boundary is the "
                          "application's responsibility, and a deleted "
                          "incident can orphan a request's reference."),
}

DOCUMENT_DB_CHARACTERISTICS = {
    "schema_flexibility": ("Documents in a collection need not share a "
                           "field set. MedSupply's FLOOD and CHEMICAL_SPILL "
                           "incidents share only the envelope fields."),
    "denormalization": ("Related data is embedded rather than joined. The "
                        "incident location is a subdocument, not a foreign "
                        "key to a locations table."),
    "no_joins": ("MongoDB's $lookup exists but is limited. Cross-collection "
                 "work is normally avoided by embedding."),
    "horizontal_scaling": ("Sharding by shard key is native. PostgreSQL "
                           "requires extensions such as Citus."),
    "bson": ("Binary JSON: typed values (dates, ints, ObjectId) rather than "
             "JSON's untyped strings and numbers."),
    "transactions": ("Multi-document ACID transactions exist since 4.0 but "
                     "require a replica set and are slower. There is no "
                     "equivalent of SELECT ... FOR UPDATE over a filtered, "
                     "ordered set — which is precisely why allocation lives "
                     "in PostgreSQL."),
    "when_not_to_use": ("Highly relational data with many-to-many "
                        "relationships, strict referential integrity "
                        "requirements, or complex multi-table transactions. "
                        "MedSupply's core inventory is all three."),
}

COMPARISON = [
    {"aspect": "Schema", "postgresql": "Fixed, enforced by DDL",
     "mongodb": "Flexible per document"},
    {"aspect": "Transactions", "postgresql": "Full ACID, row-level locks",
     "mongodb": "Multi-document since 4.0, replica set required"},
    {"aspect": "Joins", "postgresql": "Native, optimizer-planned",
     "mongodb": "$lookup, limited"},
    {"aspect": "Referential integrity", "postgresql": "FK constraints",
     "mongodb": "Application-enforced"},
    {"aspect": "Query language", "postgresql": "SQL",
     "mongodb": "Aggregation pipeline / MQL"},
    {"aspect": "Scaling", "postgresql": "Vertical; horizontal via extensions",
     "mongodb": "Native sharding"},
    {"aspect": "Best for", "postgresql": "Consistent transactional data",
     "mongodb": "Variable-shape documents"},
]
