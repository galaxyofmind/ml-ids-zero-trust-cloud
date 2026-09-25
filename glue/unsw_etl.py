"""Convert the official-size UNSW-NB15 training split to queryable Parquet."""

import sys

from awsglue.utils import getResolvedOptions
from pyspark.sql import SparkSession, functions as F


EXPECTED_COLUMNS = [
    "id", "dur", "proto", "service", "state", "spkts", "dpkts", "sbytes", "dbytes",
    "rate", "sttl", "dttl", "sload", "dload", "sloss", "dloss", "sinpkt", "dinpkt",
    "sjit", "djit", "swin", "stcpb", "dtcpb", "dwin", "tcprtt", "synack", "ackdat",
    "smean", "dmean", "trans_depth", "response_body_len", "ct_srv_src", "ct_state_ttl",
    "ct_dst_ltm", "ct_src_dport_ltm", "ct_dst_sport_ltm", "ct_dst_src_ltm",
    "is_ftp_login", "ct_ftp_cmd", "ct_flw_http_mthd", "ct_src_ltm", "ct_srv_dst",
    "is_sm_ips_ports", "attack_cat", "label",
]


def main() -> None:
    args = getResolvedOptions(sys.argv, ["RAW_URI", "CURATED_URI"])
    spark = SparkSession.builder.getOrCreate()
    raw = spark.read.option("header", "true").option("mode", "FAILFAST").csv(args["RAW_URI"])
    if raw.columns != EXPECTED_COLUMNS:
        raise ValueError(f"UNSW-NB15 schema mismatch: {raw.columns}")
    rows = raw.count()
    if rows != 175341:
        raise ValueError(f"Expected 175341 UNSW-NB15 training records, got {rows}")
    invalid = raw.filter(~F.col("label").isin("0", "1") | F.col("label").isNull()).count()
    if invalid:
        raise ValueError(f"Found {invalid} invalid binary labels")

    curated = (
        raw.withColumn("flow_id", F.sha2(F.concat_ws("|", *[F.col(c) for c in EXPECTED_COLUMNS]), 256))
        .withColumn("binary_label", F.when(F.col("label") == "0", "normal").otherwise("attack"))
        .withColumn("attack_family", F.when(F.col("label") == "0", "Normal")
                    .otherwise(F.trim(F.col("attack_cat"))))
        .withColumn("dataset_id", F.lit("unsw-nb15"))
        .withColumn("dataset_version", F.lit("v1"))
    )
    curated.coalesce(2).write.mode("overwrite").parquet(args["CURATED_URI"])
    print(f"Curated UNSW-NB15 records: {rows}")
    print(f"Curated URI: {args['CURATED_URI']}")


if __name__ == "__main__":
    main()
