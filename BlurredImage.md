<!-- !b
kind: post
service: blogger
title: Blurred Image Renderer for Xamarin.Forms
url: http://blog.adamkemp.com/2015/05/blurred-image-renderer-for-xamarinforms.html
labels: mobile, xamarin.forms, ios, android, blurred, image
blog: 6425054342484936402
draft: False
id: 7527776577702219916
-->

In response to a [recent Xamarin forum post](http://forums.xamarin.com/discussion/40994/how-can-i-blur-an-image) I spent some time building a custom Xamarin.Forms renderer for a [blurred image on iOS and Android](https://github.com/TheRealAdamKemp/BlurredImageTest). Read on to learn how I did it.

<!--more-->

[TOC]

The Problem
===========

The request was to have a blurred image view on Android. Since this is Xamarin.Forms we may as well do it for iOS as well[^WP]. The ideal is to have a drop-in replacement for the `Image` view.

The end results look like this:

![Android Screenshot](./BlurredImageViewAndroidScreenshot.png)
![iOS Screenshot](./BlurredImageViewiOSScreenshot.png)

[^WP]: I don't know how to do it for Windows Phone or WinRT, but pull requests are welcome!

Custom Image View
=================

The first step is to create a custom subclass of the `Image` view class. We don't need any new properties so it's this easy:

    :::csharp
    public class BlurredImage : Image
    {
    }

iOS Renderer Implementation
==================

I started out by trying a [`UIVisualEffectView`](https://developer.apple.com/library/ios/documentation/UIKit/Reference/UIVisualEffectView/index.html). This is very easy to use, fast, and supports blurring any views (even dynamic ones), but it turned out not to match the desired results. It was _too_ blurred, and also lightened or darkened the results. Not quite what we were after.

After some googling I came across [this StackOverflow post](http://stackoverflow.com/a/17041983) that explains how to blur an image using CoreImage. That was exactly what I wanted. I just had to translate it to C#. Fortunately that's pretty easy. Here's the result:

    :::csharp
    private class BlurredImageView : UIImageView
    {
        public override UIImage Image
        {
            get { return base.Image; }
            set
            {
                // This may take up to a second so don't block the UI thread.
                Task.Run(() =>
                    {
                        using (var context = CIContext.Create())
                        using (var inputImage = CIImage.FromCGImage(value.CGImage))
                        using (var filter = new CIGaussianBlur() { Image = inputImage, Radius = 5 })
                        using (var resultImage = context.CreateCGImage(filter.OutputImage, inputImage.Extent))
                        {
                            InvokeOnMainThread(() => base.Image = new UIImage(resultImage));
                        }
                    });
            }
        }
    }

I use this simple subclass of `UIImageView` in a simple subclass of the default `ImageRenderer` like so:

    :::csharp
    public class BlurredImageRenderer : ImageRenderer
    {
        protected override void OnElementChanged(ElementChangedEventArgs<Image> e)
        {
            if (Control == null)
            {
                SetNativeControl(new BlurredImageView
                    {
                        ContentMode = UIViewContentMode.ScaleAspectFit,
                        ClipsToBounds = true
                    });
            }

            base.OnElementChanged(e);
        }

        // ... BlurredImageView class goes here
    }

Android Renderer Implementation
===============================

For Android the core blurring routine came from [this Xamarin recipe](http://developer.xamarin.com/recipes/android/other_ux/drawing/blur_an_image_with_renderscript/), which was found by the forum member making the request. That's easy enough to use, but unfortunately I hit a snag. The default `ImageRenderer` on Android is really poorly suited for subclassing. It uses an internal custom `ImageView` subclass, which means the trick I used in iOS for blurring the image as it's applied to the view won't work. Instead I had to basically copy all of the default code.

This is a good time to mention a trick that I've been using to learn how Xamarin.Forms works: The Xamarin Studio Assembly Browser. You can get to it by either using "Go to Declaration" on a class that's in Xamarin.Forms (or some other external assembly) or by finding an assembly in your project's list of references and double-clicking it. Once in the Assembly Browser I always immediately change the "Visibility" dropdown to "All Members" and the "Language" dropdown to "C#". Then I can basically see all of the source code (decompiled) of Xamarin.Forms. Using this technique you can learn a huge amount about how things work under the hood, diagnose bugs, find workarounds, etc.

In this case I needed to know how to reimplement my own version of the `ImageRenderer` class and insert my own step to blur the image. For that I just basically copied the whole thing.

Of course it's not quite that easy. The base implementation used some internal code that I don't have access to. First, the `FormsImageView`, which does some kind of optimization for skipping invalidation in some situations. For that I just had to make my own `BlurredImageView` that does the same thing and update code as necessary to use my view.

Next I had to deal with loading images. As I discovered in [this post](https://forums.xamarin.com/discussion/comment/112460/#Comment_112460) the actual classes involved in loading platform-specific image from an `ImageSource` are all public, but the nice convenience method for finding the right implementation and doing the load is internal. Therefore I had to write a quick implementation myself, much like the iOS implementation I had written:

    :::csharp
    IImageSourceHandler handler;

    if (imageSource is FileImageSource)
    {
        handler = new FileImageSourceHandler();
    }
    else if (imageSource is StreamImageSource)
    {
        handler = new StreamImagesourceHandler(); // sic
    }
    else if (imageSource is UriImageSource)
    {
        handler = new ImageLoaderSourceHandler(); // sic
    }
    else
    {
        throw new NotImplementedException();
    }

    var originalBitmap = await handler.LoadImageAsync(imageSource, context);

Now I can load an image, but I still want to blur it. For that I just added to the above method:

    :::csharp
    var blurredBitmap = await Task.Run(() => CreateBlurredImage(originalBitmap, 25));
    return blurredBitmap;

And the `CreateBlurredImage` method comes from the [Xamarin recipe](http://developer.xamarin.com/recipes/android/other_ux/drawing/blur_an_image_with_renderscript/):

    :::csharp
    private Bitmap CreateBlurredImage(Bitmap originalBitmap, int radius)
    {
        // Create another bitmap that will hold the results of the filter.
        Bitmap blurredBitmap;
        blurredBitmap = Bitmap.CreateBitmap(originalBitmap);

        // Create the Renderscript instance that will do the work.
        RenderScript rs = RenderScript.Create(Context);

        // Allocate memory for Renderscript to work with
        Allocation input = Allocation.CreateFromBitmap(rs, originalBitmap, Allocation.MipmapControl.MipmapFull, AllocationUsage.Script);
        Allocation output = Allocation.CreateTyped(rs, input.Type);

        // Load up an instance of the specific script that we want to use.
        ScriptIntrinsicBlur script = ScriptIntrinsicBlur.Create(rs, Android.Renderscripts.Element.U8_4(rs));
        script.SetInput(input);

        // Set the blur radius
        script.SetRadius(radius);

        // Start Renderscript working.
        script.ForEach(output);

        // Copy the output to the blurred bitmap
        output.CopyTo(blurredBitmap);

        return blurredBitmap;
    }

The next problem was the use of an internal field of the `Image` class for setting an otherwise read-only property: the `IsLoading` property. The only workaround for this, unfortunately, is reflection. For that I added this code:

    :::csharp
    private static FieldInfo _isLoadingPropertyKeyFieldInfo;

    private static FieldInfo IsLoadingPropertyKeyFieldInfo
    {
        get
        {
            if (_isLoadingPropertyKeyFieldInfo == null)
            {
                _isLoadingPropertyKeyFieldInfo = typeof(Image).GetField("IsLoadingPropertyKey", BindingFlags.Static | BindingFlags.NonPublic);
            }
            return _isLoadingPropertyKeyFieldInfo;
        }
    }

    private void SetIsLoading(bool value)
    {
        var fieldInfo = IsLoadingPropertyKeyFieldInfo;
        ((IElementController)base.Element).SetValueFromRenderer((BindablePropertyKey)fieldInfo.GetValue(null), value);
    }

With that code in place I just had to do some simple substitutions to make the rest of the code compile and run. The rest of the code isn't all that interested so I've left it out, but for the complete source see the [GitHub project](https://github.com/TheRealAdamKemp/BlurredImageTest).

Caveats
=======

The Android implementation is brittle because it duplicates code from the base implementation, and it uses reflection.

That's it! Check out the [GitHub project](https://github.com/TheRealAdamKemp/BlurredImageTest). Enjoy!
