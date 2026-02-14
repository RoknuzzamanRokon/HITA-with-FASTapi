#!/usr/bin/env python3

"""
Script to ensure blog tables exist and test blog functionality
"""

import sys
import os
sys.path.append('.')

from database import engine, Base
from models import BlogPost, BlogCategory, BlogTag, BlogPostTag, BlogAnalytics
from sqlalchemy import inspect
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    try:
        logger.info('🔧 Starting blog table setup...')
        
        # Test database connection
        logger.info('📡 Testing database connection...')
        with engine.connect() as conn:
            logger.info('✅ Database connection successful')
        
        # Check if blog tables exist
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        logger.info(f'📋 Found {len(tables)} tables in database')
        
        blog_tables = ['blog_posts', 'blog_categories', 'blog_tags', 'blog_post_tags', 'blog_analytics']
        missing_tables = []
        
        for table in blog_tables:
            if table in tables:
                logger.info(f'✅ {table} table exists')
            else:
                logger.warning(f'❌ {table} table missing')
                missing_tables.append(table)
        
        if missing_tables:
            logger.info('🔧 Creating missing blog tables...')
            Base.metadata.create_all(bind=engine)
            logger.info('✅ Blog tables created successfully')
        else:
            logger.info('✅ All blog tables already exist')
        
        # Test creating some default categories if none exist
        from sqlalchemy.orm import Session
        from datetime import datetime
        import uuid
        
        session = Session(engine)
        try:
            category_count = session.query(BlogCategory).count()
            if category_count == 0:
                logger.info('📁 Creating default blog categories...')
                
                default_categories = [
                    {"name": "Tutorial", "description": "Step-by-step guides and tutorials"},
                    {"name": "Performance", "description": "Performance optimization tips"},
                    {"name": "Security", "description": "Security best practices"},
                    {"name": "Development", "description": "Development insights and updates"},
                ]
                
                for category_data in default_categories:
                    category = BlogCategory(
                        id=str(uuid.uuid4()),
                        name=category_data["name"],
                        slug=category_data["name"].lower().replace(" ", "-"),
                        description=category_data["description"],
                        created_at=datetime.utcnow()
                    )
                    session.add(category)
                
                session.commit()
                logger.info(f'✅ Created {len(default_categories)} default categories')
            else:
                logger.info(f'✅ Found {category_count} existing categories')
                
        finally:
            session.close()
        
        logger.info('✅ Blog setup completed successfully!')
        
    except Exception as e:
        logger.error(f'❌ Error during blog setup: {e}')
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())