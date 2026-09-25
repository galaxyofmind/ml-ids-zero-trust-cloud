"""Transform NSL-KDD raw CSV to a small, queryable Parquet dataset in AWS Glue."""

import sys

from awsglue.utils import getResolvedOptions
from pyspark.sql import SparkSession, functions as F


COLUMNS = [
    "duration", "protocol_type", "service", "flag", "src_bytes", "dst_bytes",
    "land", "wrong_fragment", "urgent", "hot", "num_failed_logins",
    "logged_in", "num_compromised", "root_shell", "su_attempted", "num_root",
    "num_file_creations", "num_shells", "num_access_files", "num_outbound_cmds",
    "is_host_login", "is_guest_login", "count", "srv_count", "serror_rate",
    "srv_serror_rate", "rerror_rate", "srv_rerror_rate", "same_srv_rate",
    "diff_srv_rate", "srv_diff_host_rate", "dst_host_count", "dst_host_srv_count",
    "dst_host_same_srv_rate", "dst_host_diff_srv_rate",
    "dst_host_same_src_port_rate", "dst_host_srv_diff_host_rate",
    "dst_host_serror_rate", "dst_host_srv_serror_rate", "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate", "label", "difficulty",
]

DOS = ["back", "land", "neptune", "pod", "smurf", "teardrop", "apache2", "udpstorm", "processtable", "worm", "mailbomb"]
PROBE = ["ipsweep", "nmap", "portsweep", "satan", "mscan", "saint"]
R2L = ["ftp_write", "guess_passwd", "imap", "multihop", "phf", "spy", "warezclient", "warezmaster", "sendmail", "named", "snmpgetattack", "snmpguess", "xlock", "xsnoop", "httptunnel"]
U2R = ["buffer_overflow", "loadmodule", "perl", "rootkit", "ps", "sqlattack", "xterm"]


def main() -> None:
    args = getResolvedOptions(sys.argv, ["RAW_URI", "CURATED_URI"])
    spark = SparkSession.builder.getOrCreate()
    raw = spark.read.option("header", "false").option("mode", "FAILFAST").csv(args["RAW_URI"])
    if len(raw.columns) != len(COLUMNS):
        raise ValueError(f"Expected {len(COLUMNS)} CSV columns, got {len(raw.columns)}")

    named = raw.toDF(*COLUMNS).withColumn("label", F.lower(F.trim(F.col("label"))))
    family = (
        F.when(F.col("label") == "normal", "Normal")
        .when(F.col("label").isin(DOS), "DoS")
        .when(F.col("label").isin(PROBE), "Probe")
        .when(F.col("label").isin(R2L), "R2L")
        .when(F.col("label").isin(U2R), "U2R")
        .otherwise("Unknown")
    )
    curated = (
        named.withColumn("flow_id", F.sha2(F.concat_ws("|", *[F.col(c) for c in COLUMNS]), 256))
        .withColumn("binary_label", F.when(F.col("label") == "normal", "normal").otherwise("attack"))
        .withColumn("attack_family", family)
        .withColumn("dataset_id", F.lit("nsl-kdd"))
        .withColumn("dataset_version", F.lit("v1"))
    )
    unknown = curated.filter(F.col("attack_family") == "Unknown").count()
    if unknown:
        raise ValueError(f"Found {unknown} records with unrecognized labels")
    row_count = curated.count()
    if row_count != 125973:
        raise ValueError(f"Expected 125973 records, got {row_count}")

    curated.coalesce(1).write.mode("overwrite").parquet(args["CURATED_URI"])
    print(f"Curated NSL-KDD records: {row_count}")
    print(f"Curated URI: {args['CURATED_URI']}")


if __name__ == "__main__":
    main()
