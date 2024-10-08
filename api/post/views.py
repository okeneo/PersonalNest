from account.permissions import IsAdmin, IsAuthor, IsOwnerOfObject, ReadOnly
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Category, Comment, Post, Tag
from .serializers import (
    CategorySerializer,
    CommentTreeSerializer,
    PostDetailSerializer,
    PostWriteSerializer,
    TagSerializer,
)


class PostListView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (ReadOnly | (IsAuthenticated & IsAuthor),)

    @swagger_auto_schema(
        tags=["post"],
        responses={
            200: PostDetailSerializer(many=True),
        },
    )
    def get(self, request, *args, **kwargs):
        """Get all posts."""
        posts = Post.objects.all()
        serializer = PostDetailSerializer(posts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=["post"],
        request_body=PostWriteSerializer,
        responses={
            201: PostWriteSerializer,
            400: "Bad Request",
            401: "Unauthorized Request",
        },
    )
    def post(self, request, *args, **kwargs):
        """Create a new post.

        The user must be authenticated and be an author.
        """
        serializer = PostWriteSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PostDetailView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (ReadOnly | (IsAuthenticated & (IsAdmin | IsAuthor)),)

    @swagger_auto_schema(
        tags=["post"],
        response={
            200: PostDetailSerializer,
            401: "Unauthorized Request",
            404: "Post Not Found",
        },
    )
    def get(self, request, pk, *args, **kwargs):
        """Get a specific post."""
        post = get_object_or_404(Post, pk=pk)
        serializer = PostDetailSerializer(post)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=["post"],
        response={
            200: PostWriteSerializer,
            400: "Bad Request",
            401: "Unauthorized Request",
            404: "Post Not Found",
        },
    )
    def put(self, request, pk, *args, **kwargs):
        """Update a post.

        The user must be authenticated and must be an admin or the author of the post.
        """
        post = get_object_or_404(Post, pk=pk)
        self.check_object_permissions(request, post)

        serializer = PostWriteSerializer(post, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=["post"],
        response={
            200: "Sucessful Response",
            401: "Unauthorized Request",
            404: "Post Not Found",
        },
    )
    def delete(self, request, pk, *args, **kwargs):
        """Delete a post.

        The user must be authenticated and must be an admin or the author of the post.
        """
        post = get_object_or_404(Post, pk=pk)
        self.check_object_permissions(request, post)

        post.delete()
        return Response({"detail": "Post deleted successfully."}, status=status.HTTP_200_OK)


class PublishPostView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated & (IsAdmin | IsAuthor),)

    @swagger_auto_schema(
        tags=["post"],
        responses={
            200: "Successful Response",
            400: "Bad Request",
            401: "Unauthorized Request",
            404: "Post Not Found",
        },
    )
    def post(self, request, pk, *args, **kwargs):
        """Publish an existing post.

        The user must be authenticated and must be an admin or the author of the post.
        """
        post = get_object_or_404(Post, pk=pk)
        self.check_object_permissions(request, post)

        if not post.published:
            post.published = True
            post.publish_date = timezone.now()
            post.save()

            serializer = PostDetailSerializer(post)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "The post is already published."}, status=status.HTTP_400_BAD_REQUEST
            )


class PostCommentsView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticatedOrReadOnly,)

    @swagger_auto_schema(
        tags=["comment"],
        responses={
            200: CommentTreeSerializer(many=True),
        },
    )
    def get(self, request, pk, *args, **kwargs):
        """Get all comments under a post."""
        post = get_object_or_404(Post, pk=pk)
        top_level_comments = Comment.objects.filter(post=post, parent_comment__isnull=True)
        serializer = CommentTreeSerializer(top_level_comments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=["comment"],
        responses={
            201: CommentTreeSerializer(many=True),
        },
    )
    def post(self, request, pk, *args, **kwargs):
        """Create a new comment under a post.

        The user must be authenticated.
        """
        pass


class CommentDetailView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (ReadOnly | (IsAuthenticated & IsOwnerOfObject),)

    def get(self, request, pk, *args, **kwargs):
        pass

    def put(self, request, pk, *args, **kwargs):
        pass

    @swagger_auto_schema(
        tags=["comment"],
        responses={
            200: "Successful Response",
            401: "Unauthorized Request",
            404: "Comment Not Found",
        },
    )
    def delete(self, request, pk, *args, **kwargs):
        """Delete a comment.

        The user must be authenticated and be the owner of the post.
        """
        comment = get_object_or_404(Comment, pk=pk)
        self.check_object_permissions(request, comment)

        if comment.replies.exist():
            comment.soft_delete()
        else:
            comment.delete()


class CategoryListView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (ReadOnly | (IsAuthenticated & IsAdmin),)

    @swagger_auto_schema(
        tags=["category"],
        responses={
            200: CategorySerializer(many=True),
        },
    )
    def get(self, request, *args, **kwargs):
        """Get all categories."""
        categories = Category.objects.all()
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=["category"],
        request_body=CategorySerializer,
        responses={
            201: CategorySerializer,
            400: "Bad Request",
        },
    )
    def post(self, request, *args, **kwargs):
        """Create a new Category.

        The user must be authenticated and must be an admin.
        """
        serializer = CategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CategoryDetailView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (ReadOnly | (IsAuthenticated & IsAdmin),)

    @swagger_auto_schema(
        tags=["category"],
        response={
            200: CategorySerializer,
            401: "Unauthorized Request",
            404: "Category Not Found",
        },
    )
    def get(self, request, pk, *args, **kwargs):
        """Get a category."""
        category = get_object_or_404(Category, pk=pk)
        serializer = CategorySerializer(category)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=["category"],
        response={
            200: CategorySerializer,
            400: "Bad Request",
            401: "Unauthorized Request",
            404: "Category Not Found",
        },
    )
    def put(self, request, pk, *args, **kwargs):
        """Update a category.

        The user must be authenticated and must be an admin.
        """
        category = get_object_or_404(Category, pk=pk)
        serializer = CategorySerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=["category"],
        response={
            200: "Sucessful Response",
            401: "Unauthorized Request",
            404: "Category Not Found",
        },
    )
    def delete(self, request, pk, *args, **kwargs):
        """Delete a category.

        The user must be authenticated and must be an admin.
        """
        category = get_object_or_404(Category, pk=pk)
        category.delete()
        return Response({"detail": "Category deleted successfully."}, status=status.HTTP_200_OK)


class TagListView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (ReadOnly | (IsAuthenticated & IsAdmin),)

    @swagger_auto_schema(
        tags=["tag"],
        responses={
            200: TagSerializer(many=True),
        },
    )
    def get(self, request, *args, **kwargs):
        """Get all tags."""
        tags = Tag.objects.all()
        serializer = TagSerializer(tags, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=["tag"],
        request_body=TagSerializer,
        responses={
            201: TagSerializer,
            400: "Bad Request",
        },
    )
    def post(self, request, *args, **kwargs):
        """Create a new tag.

        The user must be authenticated and must be an admin.
        """
        serializer = TagSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TagDetailView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (ReadOnly | (IsAuthenticated & IsAdmin),)

    @swagger_auto_schema(
        tags=["tag"],
        response={
            200: TagSerializer,
            401: "Unauthorized Request",
            404: "Tag Not Found",
        },
    )
    def get(self, request, pk, *args, **kwargs):
        """Get a tag."""
        tag = get_object_or_404(Tag, pk=pk)
        serializer = TagSerializer(tag)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=["tag"],
        response={
            200: TagSerializer,
            400: "Bad Request",
            401: "Unauthorized Request",
            404: "Tag Not Found",
        },
    )
    def put(self, request, pk, *args, **kwargs):
        """Update a tag.

        The user must be authenticated and must be an admin.
        """
        tag = get_object_or_404(Tag, pk=pk)
        serializer = TagSerializer(tag, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=["tag"],
        response={
            200: "Sucessful Response",
            401: "Unauthorized Request",
            404: "Tag Not Found",
        },
    )
    def delete(self, request, pk, *args, **kwargs):
        """Delete a tag.

        The user must be authenticated and must be an admin.
        """
        tag = get_object_or_404(Tag, pk=pk)
        tag.delete()
        return Response({"detail": "Tag deleted successfully."}, status=status.HTTP_200_OK)
