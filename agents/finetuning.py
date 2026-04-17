"""Fine-tuning pipeline for domain-specific Claude models on Indian legal law."""
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple


class FineTuneDataset:
    """Manages training data for fine-tuning Claude on Indian legal analysis."""
    
    def __init__(self, data_dir: str = "./data/finetuning"):
        """
        Initialize fine-tuning dataset manager.
        
        Args:
            data_dir: Directory to store training data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cases_file = self.data_dir / "landmark_cases.jsonl"
        self.training_examples = self.data_dir / "training_examples.jsonl"
        self.validation_set = self.data_dir / "validation_set.jsonl"
    
    def add_landmark_case(self, case_info: dict) -> bool:
        """
        Add a landmark legal case to training data.
        
        Args:
            case_info: Dict with case details
                - case_name: "Kesavananda Bharati v. State of Kerala"
                - year: 1973
                - court: "Supreme Court"
                - constitutional_provision: "Article 31C"
                - issue: "Property rights violation"
                - holding: "Basic structure doctrine upheld"
                - key_principle: "Parliament cannot amend basic features"
                - precedent_strength: "binding" | "persuasive"
                - applicable_domains: ["constitutional", "admin_law"]
        
        Returns:
            True if added successfully
        """
        try:
            with open(self.cases_file, 'a') as f:
                case_info["added_at"] = datetime.now().isoformat()
                f.write(json.dumps(case_info) + '\n')
            return True
        except Exception as e:
            print(f"Error adding case: {e}")
            return False
    
    def add_training_example(self, example: dict) -> bool:
        """
        Add a training example (GO analysis) to dataset.
        
        Args:
            example: Dict with:
                - system_role: "constitutional_expert" | "admin_law_expert" | etc
                - input_go: Government order text or metadata
                - expected_analysis: Expert's analysis output (JSON)
                - legal_provisions_cited: List of applicable laws
                - issues_identified: List of issues
                - reasoning: Expert's reasoning
        
        Returns:
            True if added
        """
        try:
            with open(self.training_examples, 'a') as f:
                example["added_at"] = datetime.now().isoformat()
                f.write(json.dumps(example) + '\n')
            return True
        except Exception as e:
            print(f"Error adding example: {e}")
            return False
    
    def load_cases(self) -> List[dict]:
        """Load all landmark cases."""
        cases = []
        if self.cases_file.exists():
            with open(self.cases_file) as f:
                for line in f:
                    cases.append(json.loads(line))
        return cases
    
    def load_training_examples(self) -> List[dict]:
        """Load all training examples."""
        examples = []
        if self.training_examples.exists():
            with open(self.training_examples) as f:
                for line in f:
                    examples.append(json.loads(line))
        return examples
    
    def prepare_finetuning_file(self, split_ratio: float = 0.8) -> Tuple[str, str]:
        """
        Prepare JSONL file for Anthropic fine-tuning API.
        
        File format:
        {"messages": [
            {"role": "user", "content": "Analyze this GO..."},
            {"role": "assistant", "content": "Issue 1: ..."}
        ]}
        
        Args:
            split_ratio: Train/validation split (0.8 = 80% train, 20% validate)
        
        Returns:
            Tuple of (train_file, validation_file) paths
        """
        examples = self.load_training_examples()
        if not examples:
            print("No training examples found. Add examples with add_training_example()")
            return None, None
        
        # Split data
        split_idx = int(len(examples) * split_ratio)
        train_examples = examples[:split_idx]
        val_examples = examples[split_idx:]
        
        # Format for Anthropic API
        def format_for_api(ex: dict) -> dict:
            return {
                "messages": [
                    {
                        "role": "user",
                        "content": f"""Analyze this Government Order from {ex.get('system_role', 'legal expert')} perspective.

GO: {ex.get('input_go', '')[:500]}

Identify issues, cite legal provisions, and provide analysis."""
                    },
                    {
                        "role": "assistant",
                        "content": json.dumps(ex.get('expected_analysis', {}))
                    }
                ]
            }
        
        # Write training file
        train_file = self.data_dir / "train_finetuning.jsonl"
        with open(train_file, 'w') as f:
            for ex in train_examples:
                f.write(json.dumps(format_for_api(ex)) + '\n')
        
        # Write validation file
        val_file = self.data_dir / "validation_finetuning.jsonl"
        with open(val_file, 'w') as f:
            for ex in val_examples:
                f.write(json.dumps(format_for_api(ex)) + '\n')
        
        print(f"✓ Training file: {train_file} ({len(train_examples)} examples)")
        print(f"✓ Validation file: {val_file} ({len(val_examples)} examples)")
        
        return str(train_file), str(val_file)
    
    def get_dataset_stats(self) -> dict:
        """Get statistics about the dataset."""
        cases = self.load_cases()
        examples = self.load_training_examples()
        
        # Count by domain
        domains = {}
        for case in cases:
            for domain in case.get('applicable_domains', []):
                domains[domain] = domains.get(domain, 0) + 1
        
        for ex in examples:
            role = ex.get('system_role', 'unknown')
            domains[role] = domains.get(role, 0) + 1
        
        return {
            "landmark_cases": len(cases),
            "training_examples": len(examples),
            "by_domain": domains,
            "estimated_tokens": len(cases) * 150 + len(examples) * 500,  # rough estimate
        }


class FineTuneManager:
    """Manage fine-tuning jobs via Anthropic API."""
    
    def __init__(self):
        """Initialize fine-tune manager."""
        from anthropic import Anthropic
        self.client = Anthropic()
        self.models_file = Path("./data/finetuning/models.json")
    
    def start_finetuning_job(self, train_file: str, validation_file: Optional[str] = None,
                            model: str = "claude-opus-4-1-20250805",
                            suffix: str = "legal-analysis") -> dict:
        """
        Start a fine-tuning job with Anthropic.
        
        Args:
            train_file: Path to training JSONL file
            validation_file: Path to validation JSONL file (optional)
            model: Base model to fine-tune
            suffix: Suffix for fine-tuned model name
        
        Returns:
            Job info with job_id and estimated_cost
        """
        try:
            # Upload training file
            with open(train_file, 'rb') as f:
                train_response = self.client.beta.files.upload(
                    file=(Path(train_file).name, f, "application/json"),
                )
            train_file_id = train_response.id
            print(f"✓ Training file uploaded: {train_file_id}")
            
            # Upload validation file if provided
            val_file_id = None
            if validation_file:
                with open(validation_file, 'rb') as f:
                    val_response = self.client.beta.files.upload(
                        file=(Path(validation_file).name, f, "application/json"),
                    )
                val_file_id = val_response.id
                print(f"✓ Validation file uploaded: {val_file_id}")
            
            # Start fine-tuning job
            job = self.client.beta.fine_tuning.jobs.create(
                model=model,
                training_file=train_file_id,
                validation_file=val_file_id,
                hyperparameters={
                    "learning_rate_multiplier": 1.0,
                    "batch_size": 8,
                    "n_epochs": 2,
                },
            )
            
            job_info = {
                "job_id": job.id,
                "status": job.status,
                "base_model": model,
                "fine_tuned_model": job.fine_tuned_model,
                "created_at": datetime.now().isoformat(),
                "training_file_id": train_file_id,
                "validation_file_id": val_file_id,
                "estimated_cost_usd": 0.50,  # Rough estimate
            }
            
            self._save_job(job_info)
            print(f"✓ Fine-tuning job started: {job.id}")
            return job_info
        
        except Exception as e:
            print(f"✗ Error starting fine-tuning job: {e}")
            return {"error": str(e)}
    
    def check_job_status(self, job_id: str) -> dict:
        """Check status of a fine-tuning job."""
        try:
            job = self.client.beta.fine_tuning.jobs.retrieve(job_id)
            return {
                "job_id": job.id,
                "status": job.status,  # "created" | "processing" | "succeeded" | "failed"
                "fine_tuned_model": job.fine_tuned_model,
                "result_files": job.result_files,
            }
        except Exception as e:
            return {"error": str(e)}
    
    def list_finetuned_models(self) -> List[dict]:
        """List all fine-tuned models created."""
        jobs = []
        if self.models_file.exists():
            with open(self.models_file) as f:
                jobs = json.load(f)
        return jobs
    
    def _save_job(self, job_info: dict):
        """Save job info locally."""
        jobs = []
        if self.models_file.exists():
            with open(self.models_file) as f:
                jobs = json.load(f)
        jobs.append(job_info)
        with open(self.models_file, 'w') as f:
            json.dump(jobs, f, indent=2)


# Starter data: Landmark Indian legal cases
LANDMARK_CASES = [
    {
        "case_name": "Kesavananda Bharati v. State of Kerala",
        "year": 1973,
        "court": "Supreme Court",
        "citations": ["AIR 1973 SC 1461"],
        "constitutional_provision": "Article 31C",
        "issue": "Whether Parliament can amend basic structure of Constitution",
        "holding": "Basic structure doctrine established; amendments violating basic features invalid",
        "key_principle": "Parliament cannot amend Articles 1 (sovereignty), 25-28 (freedom of religion), fundamental rights (Part III), equality before law",
        "precedent_strength": "binding",
        "applicable_domains": ["constitutional", "admin_law"],
        "quotes": ["Constitution is not a mere legal document but a social contract"]
    },
    {
        "case_name": "S.R. Bommai v. Union of India",
        "year": 1994,
        "court": "Supreme Court",
        "citations": ["AIR 1994 SC 1918"],
        "constitutional_provision": "Article 356",
        "issue": "Validity of president's dissolution of state assemblies without justification",
        "holding": "Presidential proclamation under Art 356 subject to judicial review; must be based on objective grounds",
        "key_principle": "State autonomy protected; political dismissals unconstitutional",
        "precedent_strength": "binding",
        "applicable_domains": ["constitutional", "admin_law"],
    },
    {
        "case_name": "Cellulose Products Ltd. v. Union of India",
        "year": 1971,
        "court": "Supreme Court",
        "citations": ["AIR 1971 SC 1215"],
        "constitutional_provision": "Rule of ultra vires",
        "issue": "Government order imposing restrictions beyond delegated authority",
        "holding": "Order struck down as ultra vires; delegation must be intra vires",
        "key_principle": "Delegated authority limited to scope of statute; abuse grounds for judicial intervention",
        "precedent_strength": "binding",
        "applicable_domains": ["admin_law", "fiscal_policy"],
    },
    {
        "case_name": "Olga Tellis v. Bombay Municipal Corp",
        "year": 1985,
        "court": "Supreme Court",
        "citations": ["AIR 1986 SC 180"],
        "constitutional_provision": "Article 21",
        "issue": "Eviction of slum dwellers without alternative shelter (right to life)",
        "holding": "Right to livelihood and shelter integral to Art 21; eviction without alternatives violates fundamental rights",
        "key_principle": "Economic and social rights protected under Art 21",
        "precedent_strength": "binding",
        "applicable_domains": ["public_interest", "constitutional"],
    },
    {
        "case_name": "Vishaka v. State of Rajasthan",
        "year": 1997,
        "court": "Supreme Court",
        "citations": ["AIR 1997 SC 3011"],
        "constitutional_provision": "Articles 14, 15, 21",
        "issue": "Workplace sexual harassment (gender equality and dignity violation)",
        "holding": "Workplace harassment violates Art 14/15/21; SC issued comprehensive guidelines through PIL",
        "key_principle": "SC can create substantive rights and governance norms through PIL",
        "precedent_strength": "binding",
        "applicable_domains": ["public_interest", "constitutional"],
    },
]


def bootstrap_finetuning_data():
    """Initialize fine-tuning dataset with landmark cases."""
    dataset = FineTuneDataset()
    
    for case in LANDMARK_CASES:
        dataset.add_landmark_case(case)
    
    print(f"✓ Bootstrapped {len(LANDMARK_CASES)} landmark cases for fine-tuning")
    print(f"  Location: {dataset.cases_file}")
    return dataset
