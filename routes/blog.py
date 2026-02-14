"""Blog routes with real DB persistence and public listing support."""

import logging
import re
import uuid
import os
from datetime import datetime
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session, joinedload

import models
from database import get_db
from models import BlogCategory, BlogPost, BlogTag, UserRole
from routes.auth import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1.0/blog",
    tags=["Blog Management"],
    responses={404: {"description": "Not found"}},
)


class BlogPostCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    excerpt: Optional[str] = Field(None, max_length=500)
    author: str = Field(..., min_length=1, max_length=100)
    category_id: Optional[str] = Field(None, max_length=50)
    tags: list[str] = Field(default_factory=list)
    featured_image: Optional[str] = Field(None, max_length=500)
    status: Literal["draft", "published"] = "draft"
    meta_title: Optional[str] = Field(None, max_length=255)
    meta_description: Optional[str] = Field(None, max_length=500)


class BlogPostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    excerpt: Optional[str] = Field(None, max_length=500)
    author: Optional[str] = Field(None, min_length=1, max_length=100)
    category_id: Optional[str] = Field(None, max_length=50)
    tags: Optional[list[str]] = None
    featured_image: Optional[str] = Field(None, max_length=500)
    status: Optional[Literal["draft", "published"]] = None
    meta_title: Optional[str] = Field(None, max_length=255)
    meta_description: Optional[str] = Field(None, max_length=500)


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


def _require_admin_or_super(
    current_user: Annotated[models.User, Depends(get_current_active_user)],
) -> models.User:
    if current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin and super users can manage blog posts",
        )
    return current_user


def _generate_slug(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")


def _generate_excerpt(content: str, max_length: int = 180) -> str:
    plain = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", content)).strip()
    if len(plain) <= max_length:
        return plain
    return f"{plain[:max_length].rstrip()}..."


def _calculate_read_time(content: str) -> int:
    return max(1, round(len(content.split()) / 200))


def _serialize_post(post: BlogPost) -> dict:
    category = post.category
    return {
        "id": post.id,
        "title": post.title,
        "slug": post.slug,
        "content": post.content,
        "excerpt": post.excerpt or _generate_excerpt(post.content),
        "author": post.author,
        "category": {
            "id": category.id if category else "",
            "name": category.name if category else "Uncategorized",
            "slug": category.slug if category else "uncategorized",
        },
        "tags": [
            {"id": tag.id, "name": tag.name, "slug": tag.slug}
            for tag in (post.tags or [])
        ],
        "featured_image": post.featured_image,
        "status": post.status,
        "view_count": post.view_count or 0,
        "read_time": post.read_time or _calculate_read_time(post.content),
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "updated_at": post.updated_at.isoformat() if post.updated_at else None,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "meta_title": post.meta_title,
        "meta_description": post.meta_description,
    }


def _ensure_default_categories(db: Session) -> None:
    if db.query(BlogCategory.id).first():
        return

    for name in ["Tutorial", "Performance", "Security", "Development"]:
        db.add(
            BlogCategory(
                id=str(uuid.uuid4()),
                name=name,
                slug=_generate_slug(name),
                created_at=datetime.utcnow(),
            )
        )
    db.commit()


def _ensure_unique_slug(
    db: Session, base_slug: str, exclude_post_id: Optional[str] = None
) -> str:
    slug = base_slug
    counter = 1
    while True:
        query = db.query(BlogPost).filter(BlogPost.slug == slug)
        if exclude_post_id:
            query = query.filter(BlogPost.id != exclude_post_id)
        if not query.first():
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1


@router.get("/posts", response_model=dict)
async def get_blog_posts(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    category: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort: Literal["date", "title", "popularity"] = Query("date"),
    order: Literal["asc", "desc"] = Query("desc"),
    status_filter: Literal["published", "draft", "all"] = Query(
        "published", alias="status"
    ),
    db: Session = Depends(get_db),
):
    query = db.query(BlogPost).options(
        joinedload(BlogPost.category),
        joinedload(BlogPost.tags),
    )

    if status_filter != "all":
        query = query.filter(BlogPost.status == status_filter)

    if category:
        query = query.outerjoin(BlogCategory).filter(
            or_(
                BlogPost.category_id == category,
                BlogCategory.slug == category,
                BlogCategory.name == category,
            )
        )

    if tag:
        query = query.join(BlogPost.tags).filter(
            or_(BlogTag.id == tag, BlogTag.slug == tag, BlogTag.name == tag)
        )

    if search:
        like_term = f"%{search.strip()}%"
        query = query.filter(
            or_(BlogPost.title.ilike(like_term), BlogPost.content.ilike(like_term))
        )

    if sort == "title":
        order_col = BlogPost.title
    elif sort == "popularity":
        order_col = BlogPost.view_count
    else:
        order_col = (
            BlogPost.published_at if status_filter == "published" else BlogPost.created_at
        )

    query = query.order_by(asc(order_col) if order == "asc" else desc(order_col))

    total = query.count()
    posts = query.offset((page - 1) * limit).limit(limit).all()
    total_pages = max(1, (total + limit - 1) // limit)

    return {
        "success": True,
        "data": {
            "posts": [_serialize_post(post) for post in posts],
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
        },
    }


@router.get("/posts/{post_id}", response_model=dict)
async def get_blog_post(post_id: str, db: Session = Depends(get_db)):
    post = (
        db.query(BlogPost)
        .options(joinedload(BlogPost.category), joinedload(BlogPost.tags))
        .filter(or_(BlogPost.id == post_id, BlogPost.slug == post_id))
        .first()
    )
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found"
        )

    post.view_count = (post.view_count or 0) + 1
    db.commit()
    db.refresh(post)

    return {"success": True, "data": _serialize_post(post)}


@router.post("/posts", response_model=dict)
async def create_blog_post(
    post_data: BlogPostCreate,
    current_user: Annotated[models.User, Depends(_require_admin_or_super)],
    db: Session = Depends(get_db),
):
    if post_data.category_id:
        category = (
            db.query(BlogCategory)
            .filter(BlogCategory.id == post_data.category_id)
            .first()
        )
        if not category:
            raise HTTPException(status_code=400, detail="Invalid category_id")

    base_slug = _generate_slug(post_data.title)
    slug = _ensure_unique_slug(db, base_slug)
    now = datetime.utcnow()

    post = BlogPost(
        id=str(uuid.uuid4()),
        title=post_data.title.strip(),
        slug=slug,
        content=post_data.content,
        excerpt=post_data.excerpt or _generate_excerpt(post_data.content),
        author=post_data.author.strip() or current_user.username,
        category_id=post_data.category_id,
        featured_image=post_data.featured_image,
        status=post_data.status,
        read_time=_calculate_read_time(post_data.content),
        created_at=now,
        updated_at=now,
        published_at=now if post_data.status == "published" else None,
        meta_title=post_data.meta_title,
        meta_description=post_data.meta_description,
    )

    if post_data.tags:
        post.tags = db.query(BlogTag).filter(BlogTag.id.in_(post_data.tags)).all()

    db.add(post)
    db.commit()
    db.refresh(post)

    logger.info("Blog post created by %s: %s", current_user.username, post.title)
    return {"success": True, "data": _serialize_post(post)}


@router.put("/posts/{post_id}", response_model=dict)
async def update_blog_post(
    post_id: str,
    post_data: BlogPostUpdate,
    current_user: Annotated[models.User, Depends(_require_admin_or_super)],
    db: Session = Depends(get_db),
):
    post = (
        db.query(BlogPost)
        .options(joinedload(BlogPost.category), joinedload(BlogPost.tags))
        .filter(BlogPost.id == post_id)
        .first()
    )
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found"
        )

    updates = (
        post_data.model_dump(exclude_unset=True)
        if hasattr(post_data, "model_dump")
        else post_data.dict(exclude_unset=True)
    )

    if "category_id" in updates and updates["category_id"]:
        category = (
            db.query(BlogCategory).filter(BlogCategory.id == updates["category_id"]).first()
        )
        if not category:
            raise HTTPException(status_code=400, detail="Invalid category_id")

    if "title" in updates:
        new_slug = _generate_slug(updates["title"])
        post.slug = _ensure_unique_slug(db, new_slug, exclude_post_id=post.id)
        post.title = updates["title"].strip()

    if "content" in updates:
        post.content = updates["content"]
        post.read_time = _calculate_read_time(updates["content"])
        if "excerpt" not in updates:
            post.excerpt = _generate_excerpt(updates["content"])

    for field in [
        "excerpt",
        "author",
        "category_id",
        "featured_image",
        "meta_title",
        "meta_description",
    ]:
        if field in updates:
            setattr(post, field, updates[field])

    if "status" in updates:
        previous_status = post.status
        post.status = updates["status"]
        if previous_status != "published" and post.status == "published":
            post.published_at = datetime.utcnow()

    if "tags" in updates:
        post.tags = (
            db.query(BlogTag).filter(BlogTag.id.in_(updates["tags"])).all()
            if updates["tags"]
            else []
        )

    post.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(post)

    logger.info("Blog post updated by %s: %s", current_user.username, post.id)
    return {"success": True, "data": _serialize_post(post)}


@router.delete("/posts/{post_id}", response_model=dict)
async def delete_blog_post(
    post_id: str,
    current_user: Annotated[models.User, Depends(_require_admin_or_super)],
    db: Session = Depends(get_db),
):
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found"
        )

    db.delete(post)
    db.commit()

    logger.info("Blog post deleted by %s: %s", current_user.username, post_id)
    return {"success": True, "data": {"id": post_id}}


@router.get("/categories", response_model=dict)
async def get_categories(db: Session = Depends(get_db)):
    _ensure_default_categories(db)
    categories = db.query(BlogCategory).options(joinedload(BlogCategory.posts)).all()
    data = [
        {
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "description": cat.description,
            "post_count": len([p for p in cat.posts if p.status == "published"]),
            "created_at": cat.created_at.isoformat() if cat.created_at else None,
        }
        for cat in categories
    ]
    return {"success": True, "data": data}


@router.post("/categories", response_model=dict)
async def create_category(
    category_data: CategoryCreate,
    current_user: Annotated[models.User, Depends(_require_admin_or_super)],
    db: Session = Depends(get_db),
):
    existing = (
        db.query(BlogCategory).filter(BlogCategory.name == category_data.name).first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Category already exists")

    slug = _generate_slug(category_data.name)
    category = BlogCategory(
        id=str(uuid.uuid4()),
        name=category_data.name.strip(),
        slug=slug,
        description=category_data.description,
        created_at=datetime.utcnow(),
    )
    db.add(category)
    db.commit()
    db.refresh(category)

    logger.info("Category created by %s: %s", current_user.username, category.name)
    return {
        "success": True,
        "data": {
            "id": category.id,
            "name": category.name,
            "slug": category.slug,
            "description": category.description,
            "post_count": 0,
            "created_at": category.created_at.isoformat() if category.created_at else None,
        },
    }


@router.get("/tags", response_model=dict)
async def get_tags(db: Session = Depends(get_db)):
    tags = db.query(BlogTag).options(joinedload(BlogTag.posts)).all()
    data = [
        {
            "id": tag.id,
            "name": tag.name,
            "slug": tag.slug,
            "post_count": len([p for p in tag.posts if p.status == "published"]),
            "created_at": tag.created_at.isoformat() if tag.created_at else None,
        }
        for tag in tags
    ]
    return {"success": True, "data": data}


@router.get("/search", response_model=dict)
async def search_blog_posts(
    q: str = Query(..., min_length=1),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(BlogPost).options(joinedload(BlogPost.category), joinedload(BlogPost.tags))
    query = query.filter(BlogPost.status == "published")
    query = query.filter(
        or_(BlogPost.title.ilike(f"%{q}%"), BlogPost.content.ilike(f"%{q}%"))
    )
    if category:
        query = query.outerjoin(BlogCategory).filter(
            or_(
                BlogPost.category_id == category,
                BlogCategory.slug == category,
                BlogCategory.name == category,
            )
        )

    total = query.count()
    posts = (
        query.order_by(desc(BlogPost.published_at), desc(BlogPost.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "success": True,
        "data": {
            "posts": [_serialize_post(post) for post in posts],
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": max(1, (total + limit - 1) // limit),
        },
    }


@router.get("/analytics/stats", response_model=dict)
async def get_blog_analytics(
    _current_user: Annotated[models.User, Depends(_require_admin_or_super)],
    db: Session = Depends(get_db),
):
    total_posts = db.query(func.count(BlogPost.id)).scalar() or 0
    total_views = db.query(func.coalesce(func.sum(BlogPost.view_count), 0)).scalar() or 0

    popular_posts = (
        db.query(BlogPost)
        .options(joinedload(BlogPost.category), joinedload(BlogPost.tags))
        .filter(BlogPost.status == "published")
        .order_by(desc(BlogPost.view_count), desc(BlogPost.published_at))
        .limit(5)
        .all()
    )

    popular_categories = (
        db.query(BlogCategory)
        .outerjoin(BlogCategory.posts)
        .group_by(BlogCategory.id)
        .order_by(desc(func.count(BlogPost.id)))
        .limit(5)
        .all()
    )

    return {
        "success": True,
        "data": {
            "total_posts": total_posts,
            "total_views": total_views,
            "total_subscribers": 0,
            "popular_posts": [_serialize_post(post) for post in popular_posts],
            "popular_categories": [
                {
                    "id": cat.id,
                    "name": cat.name,
                    "slug": cat.slug,
                    "description": cat.description,
                    "post_count": len([p for p in cat.posts if p.status == "published"]),
                    "created_at": cat.created_at.isoformat() if cat.created_at else None,
                }
                for cat in popular_categories
            ],
            "recent_activity": [],
        },
    }


# Image Upload Configuration
UPLOAD_DIR = "static/uploads/blog_images"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/images/upload", response_model=dict)
async def upload_blog_image(
    current_user: Annotated[models.User, Depends(_require_admin_or_super)],
    file: UploadFile = File(...),
):
    """
    Upload an image for blog posts
    """
    try:
        # Validate file type
        valid_content_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
        if file.content_type not in valid_content_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Must be one of: {', '.join(valid_content_types)}"
            )
        
        # Validate file size (5MB limit)
        max_size = 5 * 1024 * 1024  # 5MB
        if len(await file.read()) > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds 5MB limit"
            )
        
        # Reset file pointer after reading for size check
        await file.seek(0)
        
        # Generate unique filename
        file_ext = file.filename.split('.')[-1].lower()
        if file_ext not in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file extension"
            )
        
        unique_filename = f"blog_{uuid.uuid4().hex}.{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        # Generate URL
        image_url = f"/static/uploads/blog_images/{unique_filename}"
        
        logger.info("Image uploaded by %s: %s", current_user.username, unique_filename)
        
        return {
            "success": True,
            "data": {
                "url": image_url,
                "filename": unique_filename,
                "size": os.path.getsize(file_path),
                "content_type": file.content_type
            }
        }
        
    except Exception as e:
        logger.error("Failed to upload image: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload image: {str(e)}"
        )
