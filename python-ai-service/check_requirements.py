#!/usr/bin/env python3
"""
Requirements validation script
Checks if all required packages are installed with compatible versions
"""

import sys
import subprocess
from pathlib import Path
from packaging import version
import importlib.metadata

def check_requirements():
    """Check if all requirements are satisfied"""
    print("🔍 Checking Requirements Compatibility")
    print("=" * 50)
    
    requirements_file = Path(__file__).parent / "requirements.txt"
    if not requirements_file.exists():
        print("❌ requirements.txt not found")
        return False
    
    requirements = []
    with open(requirements_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                requirements.append(line)
    
    print(f"📋 Checking {len(requirements)} requirements...\n")
    
    all_good = True
    missing_packages = []
    
    for req in requirements:
        package_name = req.split('>=')[0].split('==')[0].split('[')[0]
        required_version = None
        
        # Parse version requirement
        if '>=' in req:
            required_version = req.split('>=')[1]
        elif '==' in req:
            required_version = req.split('==')[1]
        
        try:
            # Check if package is installed
            installed_version = importlib.metadata.version(package_name)
            
            # Check version compatibility
            if required_version:
                if '>=' in req:
                    if version.parse(installed_version) >= version.parse(required_version):
                        print(f"✅ {package_name}: {installed_version} (>= {required_version})")
                    else:
                        print(f"❌ {package_name}: {installed_version} < {required_version}")
                        all_good = False
                elif '==' in req:
                    if installed_version == required_version:
                        print(f"✅ {package_name}: {installed_version} (== {required_version})")
                    else:
                        print(f"⚠️  {package_name}: {installed_version} != {required_version}")
            else:
                print(f"✅ {package_name}: {installed_version}")
                
        except importlib.metadata.PackageNotFoundError:
            print(f"❌ {package_name}: NOT INSTALLED")
            missing_packages.append(req)
            all_good = False
        except Exception as e:
            print(f"❌ {package_name}: Error checking - {e}")
            all_good = False
    
    print("\n" + "=" * 50)
    
    if missing_packages:
        print(f"❌ {len(missing_packages)} packages are missing:")
        for pkg in missing_packages:
            print(f"   - {pkg}")
        print(f"\nInstall missing packages with:")
        print(f"   pip install {' '.join(missing_packages)}")
    
    if all_good:
        print("🎉 All requirements satisfied!")
        
        # Test core imports
        print("\n🧪 Testing core imports...")
        try:
            import fastapi
            import uvicorn
            import litellm
            import langchain
            import openai
            from rag_pipeline import load_vectorstore
            from ai_agent import DehumidifierAgent
            print("✅ All core modules can be imported")
            
            # Test service initialization
            agent = DehumidifierAgent()
            print(f"✅ AI Agent initialized (RAG available: {agent.tools.vectorstore is not None})")
            
        except Exception as e:
            print(f"❌ Import test failed: {e}")
            all_good = False
    else:
        print("❌ Requirements check failed!")
    
    return all_good

if __name__ == "__main__":
    success = check_requirements()
    sys.exit(0 if success else 1)